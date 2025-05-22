# picker.py
# Подбирает 10 слов для сессии опытных пользователей (Main-bucket, Stretch+1, Patch-1, Adaptive).
# Соответствует спецификации MVP v1, раздел 3.

import random
import logging
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from db_access import (
    get_db_connection, close_db_connection, get_word_translation,
    get_wrong_translation, get_recent_success_rate
)
from config import CONFIG, LEVEL_TO_DIFFICULTY, LEVEL_ORDER

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def select_words(user_id, target_language_id, user_language_id, level, translation_language_id=2):
    """Выбирает 10 слов для сессии, возвращает список с переводами."""
    try:
        logger.info(f"Selecting words for user {user_id}, level {level}")
        
        # Словарь для подсчета слов по категориям
        categories_count = {
            "Weak": 0,
            "Review": 0,
            "New-L": 0,
            "Stretch+1": 0,
            "Patch-1": 0,
            "Fallback": 0
        }
        
        # Подготовка параметров
        current_difficulty = LEVEL_TO_DIFFICULTY[level]
        stretch_difficulty = current_difficulty + 1 if level != "C2" else None
        patch_difficulty = current_difficulty - 1 if level != "A1" else None
        
        # Получаем recent_success_rate для Adaptive и блокировки новых слов
        recent_success_rate = get_recent_success_rate(user_language_id, num_answers=20)
        
        # Более гибкая логика определения количества новых слов
        if recent_success_rate < CONFIG["NEW_WORDS_THRESHOLD_LOW"]:
            max_new_words_limit = CONFIG["NEW_WORDS_COUNT_LOW"]
        elif recent_success_rate < CONFIG["NEW_WORDS_THRESHOLD_MID"]:
            max_new_words_limit = CONFIG["NEW_WORDS_COUNT_MID"]
        elif recent_success_rate < CONFIG["NEW_WORDS_THRESHOLD_HIGH"]:
            max_new_words_limit = CONFIG["NEW_WORDS_COUNT_HIGH"]
        else:
            max_new_words_limit = CONFIG["NEW_WORDS_COUNT_VERY_HIGH"]
        
        logger.info(f"User recent_success_rate: {recent_success_rate}%, max_new_words_limit: {max_new_words_limit}")

        conn = get_db_connection()
        words = []
        selected_word_ids = []

        try:
            with conn:
                with conn.cursor() as cur:
                    # Основная логика подбора слов
                    
                    # 1. Предварительно соберем слова по категориям
                    weak_words = []
                    review_words = []
                    new_words = []
                    stretch_words = []
                    patch_words = []
                    
                    # Сбор Weak слов (с более гибким порогом)
                    cur.execute("""
                        SELECT w.id, w.text
                        FROM words w
                        JOIN user_progress up ON w.id = up.word_id
                        WHERE up.user_language_id = %s
                        AND w.difficulty = %s
                        AND (up.success_rate < %s OR up.last_answer_wrong = TRUE)
                        ORDER BY up.success_rate ASC, RANDOM()
                        LIMIT 5
                    """, (user_language_id, current_difficulty, CONFIG["WEAK_SUCCESS_THRESHOLD"]))
                    weak_words = cur.fetchall()
                    
                    # Если не нашли достаточно слабых слов - используем fallback порог
                    if len(weak_words) < 3:
                        logger.warning(
                            f"Only {len(weak_words)} Weak words found with threshold {CONFIG['WEAK_SUCCESS_THRESHOLD']}%, " +
                            f"trying fallback threshold {CONFIG['WEAK_SUCCESS_FALLBACK']}%"
                        )
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            JOIN user_progress up ON w.id = up.word_id
                            WHERE up.user_language_id = %s
                            AND w.difficulty = %s
                            AND up.success_rate < %s
                            AND w.id NOT IN (SELECT unnest(%s::int[]))
                            ORDER BY up.success_rate ASC, RANDOM()
                            LIMIT %s
                        """, (
                            user_language_id, 
                            current_difficulty, 
                            CONFIG["WEAK_SUCCESS_FALLBACK"],
                            [w['id'] for w in weak_words] if weak_words else [], 
                            5 - len(weak_words)
                        ))
                        weak_words.extend(cur.fetchall())
                        
                        # Если всё ещё не хватает - используем последний запасной порог
                        if len(weak_words) < 2:
                            logger.warning(
                                f"Still only {len(weak_words)} Weak words found, " + 
                                f"trying last resort threshold {CONFIG['WEAK_SUCCESS_LAST_RESORT']}%"
                            )
                            cur.execute("""
                                SELECT w.id, w.text
                                FROM words w
                                JOIN user_progress up ON w.id = up.word_id
                                WHERE up.user_language_id = %s
                                AND w.difficulty = %s
                                AND up.success_rate < %s
                                AND w.id NOT IN (SELECT unnest(%s::int[]))
                                ORDER BY up.success_rate ASC, RANDOM()
                                LIMIT %s
                            """, (
                                user_language_id, 
                                current_difficulty, 
                                CONFIG["WEAK_SUCCESS_LAST_RESORT"],
                                [w['id'] for w in weak_words] if weak_words else [], 
                                5 - len(weak_words)
                            ))
                            weak_words.extend(cur.fetchall())
                    
                    # Сбор Review слов - базируемся на давности просмотра
                    cur.execute("""
                        SELECT w.id, w.text
                        FROM words w
                        JOIN user_progress up ON w.id = up.word_id
                        WHERE up.user_language_id = %s
                        AND w.difficulty = %s
                        AND up.success_rate >= %s
                        AND up.last_seen < %s
                        AND w.id NOT IN (SELECT unnest(%s::int[]))
                        ORDER BY up.last_seen ASC, RANDOM()
                        LIMIT 4
                    """, (
                        user_language_id, 
                        current_difficulty, 
                        CONFIG["REVIEW_SUCCESS_THRESHOLD"],
                        datetime.now() - timedelta(days=CONFIG["LAST_SEEN_DAYS_SHORT"]),
                        [w['id'] for w in weak_words] if weak_words else []
                    ))
                    review_words = cur.fetchall()
                    
                    # Если мало Review слов - смягчаем критерии
                    if len(review_words) < 2:
                        logger.warning(
                            f"Only {len(review_words)} Review words found with threshold {CONFIG['REVIEW_SUCCESS_THRESHOLD']}%, " +
                            f"trying fallback threshold {CONFIG['REVIEW_SUCCESS_FALLBACK']}%"
                        )
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            JOIN user_progress up ON w.id = up.word_id
                            WHERE up.user_language_id = %s
                            AND w.difficulty = %s
                            AND up.success_rate BETWEEN %s AND %s
                            AND up.last_seen < %s
                            AND w.id NOT IN (SELECT unnest(%s::int[]))
                            ORDER BY up.last_seen ASC, RANDOM()
                            LIMIT %s
                        """, (
                            user_language_id, 
                            current_difficulty, 
                            CONFIG["REVIEW_SUCCESS_FALLBACK"], 
                            CONFIG["REVIEW_SUCCESS_THRESHOLD"] - 1,
                            datetime.now() - timedelta(days=CONFIG["LAST_SEEN_DAYS_MEDIUM"]),
                            [w['id'] for w in weak_words + review_words] if (weak_words or review_words) else [],
                            4 - len(review_words)
                        ))
                        review_words.extend(cur.fetchall())
                        
                        # Если все еще не хватает - ищем просто по давности просмотра
                        if len(review_words) < 2:
                            logger.warning("Still not enough Review words, using time-based fallback")
                            cur.execute("""
                                SELECT w.id, w.text
                                FROM words w
                                JOIN user_progress up ON w.id = up.word_id
                                WHERE up.user_language_id = %s
                                AND w.difficulty = %s
                                AND up.last_seen < %s
                                AND w.id NOT IN (SELECT unnest(%s::int[]))
                                ORDER BY up.last_seen ASC, RANDOM()
                                LIMIT %s
                            """, (
                                user_language_id, 
                                current_difficulty,
                                datetime.now() - timedelta(days=CONFIG["LAST_SEEN_DAYS_LONG"]),
                                [w['id'] for w in weak_words + review_words] if (weak_words or review_words) else [],
                                4 - len(review_words)
                            ))
                            review_words.extend(cur.fetchall())
                    
                    # Сбор новых слов (New-L) с учетом максимального лимита
                    cur.execute("""
                        SELECT w.id, w.text
                        FROM words w
                        WHERE w.language_id = %s
                        AND w.difficulty = %s
                        AND w.id NOT IN (
                            SELECT word_id FROM user_progress WHERE user_language_id = %s
                        )
                        AND (w.id NOT IN (
                            SELECT word_id FROM user_progress
                            WHERE user_language_id = %s
                            AND last_seen > %s
                        ) OR TRUE)
                        ORDER BY w.frequency_rank ASC, RANDOM()
                        LIMIT %s
                    """, (
                        target_language_id, 
                        current_difficulty, 
                        user_language_id,
                        user_language_id, 
                        datetime.now() - timedelta(minutes=CONFIG["NEW_WORD_PAUSE_MINUTES"]),
                        max_new_words_limit
                    ))
                    new_words = cur.fetchall()
                    if len(new_words) < 1 and max_new_words_limit > 0:
                        logger.warning("No New words found in current level, trying to find in other levels")
                        # Ищем в других уровнях, начиная с ближайших
                        if stretch_difficulty:
                            cur.execute("""
                                SELECT w.id, w.text
                                FROM words w
                                WHERE w.language_id = %s
                                AND w.difficulty = %s
                                AND w.id NOT IN (
                                    SELECT word_id FROM user_progress WHERE user_language_id = %s
                                )
                                ORDER BY w.frequency_rank ASC, RANDOM()
                                LIMIT %s
                            """, (
                                target_language_id,
                                stretch_difficulty,
                                user_language_id,
                                max(1, max_new_words_limit // 2)
                            ))
                            new_words.extend(cur.fetchall())
                        
                        if patch_difficulty and len(new_words) < max_new_words_limit:
                            cur.execute("""
                                SELECT w.id, w.text
                                FROM words w
                                WHERE w.language_id = %s
                                AND w.difficulty = %s
                                AND w.id NOT IN (
                                    SELECT word_id FROM user_progress WHERE user_language_id = %s
                                )
                                AND w.id NOT IN (SELECT unnest(%s::int[]))
                                ORDER BY w.frequency_rank ASC, RANDOM()
                                LIMIT %s
                            """, (
                                target_language_id,
                                patch_difficulty,
                                user_language_id,
                                [w['id'] for w in new_words] if new_words else [],
                                max_new_words_limit - len(new_words)
                            ))
                            new_words.extend(cur.fetchall())
                    
                    # Сбор слов Stretch+1
                    if stretch_difficulty:
                        cur.execute("""
                            SELECT id, text
                            FROM words
                            WHERE language_id = %s
                            AND difficulty = %s
                            ORDER BY RANDOM()
                            LIMIT 2
                        """, (target_language_id, stretch_difficulty))
                        stretch_words = cur.fetchall()
                    
                    # Сбор слов Patch-1
                    if patch_difficulty:
                        cur.execute("""
                            SELECT id, text
                            FROM words
                            WHERE language_id = %s
                            AND difficulty = %s
                            ORDER BY RANDOM()
                            LIMIT 2
                        """, (target_language_id, patch_difficulty))
                        patch_words = cur.fetchall()
                    
                    # Формирование итоговой сессии
                    selected_word_ids = []
                    
                    # 2. Добавляем слова из категорий в оптимальных пропорциях
                    
                    # Начинаем со слабых слов (Weak)
                    weak_count = min(len(weak_words), 3)  # Максимум 3 слабых слова
                    for i in range(weak_count):
                        word = weak_words[i]
                        if word['id'] not in selected_word_ids:
                            words.append(word)
                            selected_word_ids.append(word['id'])
                            categories_count["Weak"] += 1
                    
                    # Добавляем новые слова (New-L)
                    new_count = min(len(new_words), max_new_words_limit)
                    for i in range(new_count):
                        word = new_words[i]
                        if word['id'] not in selected_word_ids:
                            words.append(word)
                            selected_word_ids.append(word['id'])
                            categories_count["New-L"] += 1
                    
                    # Добавляем слова для повторения (Review)
                    review_count = min(len(review_words), 3)  # Максимум 3 слова для повторения
                    for i in range(review_count):
                        word = review_words[i]
                        if word['id'] not in selected_word_ids:
                            words.append(word)
                            selected_word_ids.append(word['id'])
                            categories_count["Review"] += 1
                    
                    # Добавляем слова повышенной сложности (Stretch+1)
                    stretch_count = min(len(stretch_words), 2 if recent_success_rate >= CONFIG["ADAPTIVE_SUCCESS_THRESHOLD"] else 1)
                    for i in range(stretch_count):
                        word = stretch_words[i]
                        if word['id'] not in selected_word_ids:
                            words.append(word)
                            selected_word_ids.append(word['id'])
                            categories_count["Stretch+1"] += 1
                    
                    # Добавляем слова пониженной сложности (Patch-1)
                    patch_count = min(len(patch_words), 1)
                    for i in range(patch_count):
                        word = patch_words[i]
                        if word['id'] not in selected_word_ids:
                            words.append(word)
                            selected_word_ids.append(word['id'])
                            categories_count["Patch-1"] += 1
                    
                    # 3. Если не хватает слов до 10, запускаем механизм гарантированного заполнения
                    remaining = CONFIG["SESSION_SIZE"] - len(words)
                    if remaining > 0:
                        logger.warning(f"Not enough words selected, need {remaining} more. Using guaranteed filling mechanism.")
                        
                        # Стратегия 1: Оставшиеся слова из собранных категорий
                        remaining_pool = []
                        for word in weak_words + review_words + new_words + stretch_words + patch_words:
                            if word['id'] not in selected_word_ids:
                                remaining_pool.append(word)
                        
                        # Берем случайные слова из оставшегося пула
                        random.shuffle(remaining_pool)
                        for i in range(min(len(remaining_pool), remaining)):
                            words.append(remaining_pool[i])
                            selected_word_ids.append(remaining_pool[i]['id'])
                            categories_count["Fallback"] += 1
                            remaining -= 1
                        
                        # Стратегия 2: Любые слова подходящего уровня, отсортированные по давности просмотра
                        if remaining > 0:
                            logger.warning(f"Still need {remaining} more words. Using last seen sorting strategy.")
                            cur.execute("""
                                SELECT w.id, w.text
                                FROM words w
                                LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                                WHERE w.language_id = %s
                                AND w.id NOT IN (SELECT unnest(%s::int[]))
                                ORDER BY up.last_seen ASC NULLS FIRST, RANDOM()
                                LIMIT %s
                            """, (
                                user_language_id,
                                target_language_id,
                                selected_word_ids,
                                remaining
                            ))
                            fallback_words = cur.fetchall()
                            words.extend(fallback_words)
                            for word in fallback_words:
                                selected_word_ids.append(word['id'])
                                categories_count["Fallback"] += 1
                                remaining -= 1
                        
                        # Стратегия 3: Абсолютно любые слова целевого языка (крайний случай)
                        if remaining > 0:
                            logger.warning(f"CRITICAL: Still need {remaining} words. Using ANY words.")
                            cur.execute("""
                                SELECT id, text
                                FROM words
                                WHERE language_id = %s
                                AND id NOT IN (SELECT unnest(%s::int[]))
                                ORDER BY RANDOM()
                                LIMIT %s
                            """, (target_language_id, selected_word_ids, remaining))
                            last_resort_words = cur.fetchall()
                            words.extend(last_resort_words)
                            categories_count["Fallback"] += len(last_resort_words)

        finally:
            close_db_connection(conn)

        # Формируем результат с переводами
        result = []
        seen_ids = set()
        for word in words[:CONFIG["SESSION_SIZE"]]:
            word_id = word['id']
            if word_id in seen_ids:
                logger.warning(f"Duplicate word_id {word_id}, skipping")
                continue
            seen_ids.add(word_id)
            word_text = word['text']
            
            # Получаем правильный перевод
            correct_translation = get_word_translation(word_id, translation_language_id)
            if not correct_translation:
                logger.warning(f"No translation for word_id {word_id} (text: {word_text})")
                continue
            
            # Получаем неправильный перевод
            wrong_translation = get_wrong_translation(word_id, translation_language_id)
            if not wrong_translation:
                logger.warning(f"No wrong translation for word_id {word_id} (text: {word_text})")
                continue
            
            # Формируем опции и перемешиваем
            options = [correct_translation, wrong_translation]
            random.shuffle(options)
            
            result.append({
                'id': word_id,
                'text': word_text,
                'correct_translation': correct_translation,
                'options': options
            })

        # Перемешиваем слова
        random.shuffle(result)
        
        # Логируем итоговые категории
        logger.info(f"Words distribution by category: Weak: {categories_count['Weak']}, " + 
                   f"Review: {categories_count['Review']}, " + 
                   f"New-L: {categories_count['New-L']}, " + 
                   f"Stretch+1: {categories_count['Stretch+1']}, " + 
                   f"Patch-1: {categories_count['Patch-1']}, " + 
                   f"Fallback: {categories_count['Fallback']}")
        
        # Проверяем финальный размер
        if len(result) < CONFIG["SESSION_SIZE"]:
            logger.error(f"Final result: {len(result)} words, expected {CONFIG['SESSION_SIZE']}")
            # Не вызываем ошибку, а возвращаем то, что есть
            logger.info(f"Returning incomplete session with {len(result)} words")
        else:
            logger.info(f"Selected {len(result)} words for user {user_id}")
            
        return result
    
    except Exception as e:
        logger.error(f"Error in select_words: {e}")
        raise