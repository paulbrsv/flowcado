import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from psycopg2.extras import RealDictCursor
from db.database import (
    get_db_connection, close_db_connection, get_word_translation,
    get_wrong_translation, get_recent_success_rate
)
from models.config import CONFIG, LEVEL_TO_DIFFICULTY, LEVEL_ORDER

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def select_words(user_id: int, target_language_id: int, user_language_id: int, level: str, translation_language_id: int = 2) -> List[Dict[str, Any]]:
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
                    # Проверяем наличие колонки increase_patch
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns
                            WHERE table_name = 'user_languages' AND column_name = 'increase_patch'
                        )
                    """)
                    has_increase_patch = cur.fetchone()['exists']
                    
                    # Динамически настраиваем лимит patch-слов
                    patch_limit = 0
                    if patch_difficulty is not None:
                        patch_limit = 1  # По умолчанию макс. 1 patch-слово
                        
                        # Если у нас есть колонка increase_patch, проверяем её значение
                        if has_increase_patch:
                            cur.execute("""
                                SELECT increase_patch FROM user_languages
                                WHERE id = %s
                            """, (user_language_id,))
                            result = cur.fetchone()
                            if result and result['increase_patch']:
                                patch_limit = 3  # Увеличиваем до 3 patch-слов при возвращении
                    
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
                    
                    # Сбор New-L слов текущего уровня
                    cur.execute("""
                        SELECT w.id, w.text
                        FROM words w
                        LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                        WHERE w.difficulty = %s
                        AND up.id IS NULL
                        AND w.id NOT IN (SELECT unnest(%s::int[]))
                        ORDER BY RANDOM()
                        LIMIT %s
                    """, (
                        user_language_id,
                        current_difficulty,
                        [w['id'] for w in weak_words + review_words] if (weak_words or review_words) else [],
                        max_new_words_limit
                    ))
                    new_words = cur.fetchall()
                    
                    # Если не хватает New-L - ищем на сложности +1
                    if len(new_words) < 1 and stretch_difficulty:
                        logger.warning(f"Not enough New-L words, trying difficulty {stretch_difficulty}")
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                            WHERE w.difficulty = %s
                            AND up.id IS NULL
                            AND w.id NOT IN (SELECT unnest(%s::int[]))
                            ORDER BY RANDOM()
                            LIMIT %s
                        """, (
                            user_language_id,
                            stretch_difficulty,
                            [w['id'] for w in weak_words + review_words + new_words] if (weak_words or review_words or new_words) else [],
                            max_new_words_limit
                        ))
                        new_words.extend(cur.fetchall())
                    
                    # Если совсем плохо с New - ищем на сложности -1
                    if len(new_words) < 1 and patch_difficulty:
                        logger.warning(f"Still not enough New-L words, trying difficulty {patch_difficulty}")
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                            WHERE w.difficulty = %s
                            AND up.id IS NULL
                            AND w.id NOT IN (SELECT unnest(%s::int[]))
                            ORDER BY RANDOM()
                            LIMIT %s
                        """, (
                            user_language_id,
                            patch_difficulty,
                            [w['id'] for w in weak_words + review_words + new_words] if (weak_words or review_words or new_words) else [],
                            max_new_words_limit
                        ))
                        new_words.extend(cur.fetchall())
                    
                    # Сбор Stretch+1 слов (повышенная сложность)
                    if stretch_difficulty:
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                            WHERE w.difficulty = %s
                            AND (up.id IS NULL OR up.last_seen < %s)
                            AND w.id NOT IN (SELECT unnest(%s::int[]))
                            ORDER BY RANDOM()
                            LIMIT 2
                        """, (
                            user_language_id,
                            stretch_difficulty,
                            datetime.now() - timedelta(days=CONFIG["LAST_SEEN_DAYS_MEDIUM"]),
                            [w['id'] for w in weak_words + review_words + new_words] if (weak_words or review_words or new_words) else []
                        ))
                        stretch_words = cur.fetchall()
                    
                    # Сбор Patch-1 слов (пониженная сложность)
                    if patch_difficulty:
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                            WHERE w.difficulty = %s
                            AND (up.id IS NULL OR up.last_seen < %s)
                            AND w.id NOT IN (SELECT unnest(%s::int[]))
                            ORDER BY RANDOM()
                            LIMIT %s
                        """, (
                            user_language_id,
                            patch_difficulty,
                            datetime.now() - timedelta(days=CONFIG["LAST_SEEN_DAYS_LONG"]),
                            [w['id'] for w in weak_words + review_words + new_words + stretch_words] 
                                if (weak_words or review_words or new_words or stretch_words) else [],
                            patch_limit
                        ))
                        patch_words = cur.fetchall()
                    
                    # 2. Формируем финальный список слов
                    # Сколько Weak слов включаем
                    weak_to_include = min(CONFIG["WEAK_WORDS_TARGET"], len(weak_words))
                    categories_count["Weak"] = weak_to_include
                    
                    # Сколько Review слов нужно
                    review_to_include = min(CONFIG["REVIEW_WORDS_TARGET"], len(review_words))
                    categories_count["Review"] = review_to_include
                    
                    # Сколько новых слов включаем
                    new_to_include = min(max_new_words_limit, len(new_words))
                    categories_count["New-L"] = new_to_include
                    
                    # Сколько Stretch/Patch слов
                    words_count = weak_to_include + review_to_include + new_to_include
                    remaining_slots = CONFIG["SESSION_SIZE"] - words_count
                    
                    # Заполняем оставшиеся слоты из имеющихся категорий
                    if remaining_slots > 0:
                        logger.warning(f"Need {remaining_slots} more words to fill session")
                        
                        # Если остались не использованные Weak слова - приоритет им
                        unused_weak = len(weak_words) - weak_to_include
                        if unused_weak > 0:
                            add_weak = min(remaining_slots, unused_weak)
                            weak_to_include += add_weak
                            remaining_slots -= add_weak
                            categories_count["Weak"] = weak_to_include
                            logger.info(f"Added {add_weak} more Weak words")
                            
                        # Если остались не использованные Review слова
                        if remaining_slots > 0:
                            unused_review = len(review_words) - review_to_include
                            if unused_review > 0:
                                add_review = min(remaining_slots, unused_review)
                                review_to_include += add_review
                                remaining_slots -= add_review
                                categories_count["Review"] = review_to_include
                                logger.info(f"Added {add_review} more Review words")
                                
                        # Если остались не использованные New слова
                        if remaining_slots > 0:
                            unused_new = len(new_words) - new_to_include
                            if unused_new > 0:
                                add_new = min(remaining_slots, unused_new)
                                new_to_include += add_new
                                remaining_slots -= add_new
                                categories_count["New-L"] = new_to_include
                                logger.info(f"Added {add_new} more New-L words")
                                
                        # Используем stretch слова
                        if remaining_slots > 0 and stretch_words:
                            stretch_to_include = min(remaining_slots, len(stretch_words))
                            categories_count["Stretch+1"] = stretch_to_include
                            remaining_slots -= stretch_to_include
                            logger.info(f"Added {stretch_to_include} Stretch+1 words")
                            
                        # Используем patch слова
                        if remaining_slots > 0 and patch_words:
                            patch_to_include = min(remaining_slots, len(patch_words))
                            categories_count["Patch-1"] = patch_to_include
                            remaining_slots -= patch_to_include
                            logger.info(f"Added {patch_to_include} Patch-1 words")
                    
                    # Если всё ещё не хватает слов - fallback
                    if words_count + remaining_slots < CONFIG["SESSION_SIZE"]:
                        fallback_count = CONFIG["SESSION_SIZE"] - (words_count + remaining_slots)
                        logger.warning(f"Using {fallback_count} fallback words")
                        categories_count["Fallback"] = fallback_count
                        
                        # Собираем все выбранные ID слов
                        all_selected_ids = []
                        if weak_to_include > 0:
                            all_selected_ids.extend([w['id'] for w in weak_words[:weak_to_include]])
                        if review_to_include > 0:
                            all_selected_ids.extend([w['id'] for w in review_words[:review_to_include]])
                        if new_to_include > 0:
                            all_selected_ids.extend([w['id'] for w in new_words[:new_to_include]])
                        if categories_count["Stretch+1"] > 0:
                            all_selected_ids.extend([w['id'] for w in stretch_words[:categories_count["Stretch+1"]]])
                        if categories_count["Patch-1"] > 0:
                            all_selected_ids.extend([w['id'] for w in patch_words[:categories_count["Patch-1"]]])
                        
                        # Добавляем fallback слова
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            LEFT JOIN user_progress up ON w.id = up.word_id AND up.user_language_id = %s
                            WHERE w.id NOT IN (SELECT unnest(%s::int[]))
                            AND w.language_id = %s
                            ORDER BY RANDOM()
                            LIMIT %s
                        """, (
                            user_language_id,
                            all_selected_ids if all_selected_ids else [],
                            target_language_id,
                            fallback_count
                        ))
                        fallback_words = cur.fetchall()
                        
                        # Формируем итоговый список слов
                        words.extend(weak_words[:weak_to_include])
                        words.extend(review_words[:review_to_include])
                        words.extend(new_words[:new_to_include])
                        
                        if categories_count["Stretch+1"] > 0:
                            words.extend(stretch_words[:categories_count["Stretch+1"]])
                        if categories_count["Patch-1"] > 0:
                            words.extend(patch_words[:categories_count["Patch-1"]])
                            
                        words.extend(fallback_words)
                    else:
                        # Формируем итоговый список слов без fallback
                        words.extend(weak_words[:weak_to_include])
                        words.extend(review_words[:review_to_include])
                        words.extend(new_words[:new_to_include])
                        
                        if categories_count["Stretch+1"] > 0:
                            words.extend(stretch_words[:categories_count["Stretch+1"]])
                        if categories_count["Patch-1"] > 0:
                            words.extend(patch_words[:categories_count["Patch-1"]])
                    
                    # В любом случае должно получиться ровно 10 слов или пополнить fallback
                    if len(words) < CONFIG["SESSION_SIZE"]:
                        missing_count = CONFIG["SESSION_SIZE"] - len(words)
                        logger.warning(f"Still missing {missing_count} words after all selection, using emergency fallback")
                        
                        # Получаем все ID выбранных слов
                        selected_ids = [w['id'] for w in words]
                        
                        # Берем любые слова, которых еще нет в списке
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            WHERE w.id NOT IN (SELECT unnest(%s::int[]))
                            AND w.language_id = %s
                            ORDER BY RANDOM()
                            LIMIT %s
                        """, (
                            selected_ids if selected_ids else [],
                            target_language_id,
                            missing_count
                        ))
                        words.extend(cur.fetchall())
                    
                    # Если вдруг получилось больше 10 слов, обрезаем
                    if len(words) > CONFIG["SESSION_SIZE"]:
                        logger.warning(f"Too many words selected: {len(words)}, trimming to {CONFIG['SESSION_SIZE']}")
                        words = words[:CONFIG["SESSION_SIZE"]]
                    
                    # Перемешиваем слова перед выдачей
                    random.shuffle(words)
        finally:
            close_db_connection(conn)
        
        # Добавляем к каждому слову необходимые переводы
        result_words = []
        for word in words:
            word_id = word['id']
            
            # Получаем правильный перевод
            correct_translation = get_word_translation(word_id, translation_language_id)
            
            # Получаем неправильные варианты
            wrong_translations = get_wrong_translation(
                word_id, 
                current_difficulty, 
                translation_language_id, 
                count=3
            )
            
            # Собираем все варианты для ответа и перемешиваем
            options = [correct_translation] + wrong_translations
            random.shuffle(options)
            
            # Формируем итоговый объект слова
            word_result = {
                "wordId": word_id,
                "text": word['text'],
                "correctTranslation": correct_translation,
                "options": options
            }
            
            result_words.append(word_result)
        
        # Проверяем, что у нас действительно 10 слов
        if len(result_words) != CONFIG["SESSION_SIZE"]:
            logger.error(f"Final word count is {len(result_words)}, expected {CONFIG['SESSION_SIZE']}")
            # Если не хватает слов с переводами, дополним дублями (лучше так, чем меньше 10)
            while len(result_words) < CONFIG["SESSION_SIZE"] and len(result_words) > 0:
                # Клонируем первое слово
                clone = result_words[0].copy()
                result_words.append(clone)
            # Если все еще больше 10, обрежем
            if len(result_words) > CONFIG["SESSION_SIZE"]:
                result_words = result_words[:CONFIG["SESSION_SIZE"]]
        
        # Логирование количества слов по категориям
        logger.info(f"Selected words by category: {categories_count}")
        logger.info(f"Final word count: {len(result_words)}")
        
        return result_words
        
    except Exception as e:
        logger.error(f"Error selecting words: {str(e)}")
        return [] 