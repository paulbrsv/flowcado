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
        
        # Подготовка параметров
        current_difficulty = LEVEL_TO_DIFFICULTY[level]
        stretch_difficulty = current_difficulty + 1 if level != "C2" else None
        patch_difficulty = current_difficulty - 1 if level != "A1" else None
        
        # Получаем recent_success_rate для Adaptive и блокировки новых слов
        recent_success_rate = get_recent_success_rate(user_language_id, num_answers=20)
        block_new_words = recent_success_rate < CONFIG["NEW_WORDS_SUCCESS_THRESHOLD"]

        conn = get_db_connection()
        words = []

        try:
            with conn:
                with conn.cursor() as cur:
                    # 1. Main-bucket (7 слов: Weak, New-L, Review)
                    main_bucket = []
                    new_words_count = 0

                    # Weak: success_rate < 60% или last_answer_wrong
                    cur.execute("""
                        SELECT w.id, w.text
                        FROM words w
                        JOIN user_progress up ON w.id = up.word_id
                        WHERE up.user_language_id = %s
                        AND w.difficulty = %s
                        AND (up.success_rate < %s OR up.last_answer_wrong = TRUE)
                        ORDER BY up.success_rate ASC, RANDOM()
                        LIMIT 4
                    """, (user_language_id, current_difficulty, 60))
                    weak_words = cur.fetchall()
                    weak_words = weak_words[:4]  # Максимум 4 Weak
                    main_bucket.extend(weak_words)
                    if len(weak_words) < 2:
                        logger.warning(f"Only {len(weak_words)} Weak words found, expected at least 2")

                    # Review: success_rate >= 80%, interval_due
                    interval_due = timedelta(days=1) * (2 ** 1)  # Упрощённо, n=1
                    cur.execute("""
                        SELECT w.id, w.text
                        FROM words w
                        JOIN user_progress up ON w.id = up.word_id
                        WHERE up.user_language_id = %s
                        AND w.difficulty = %s
                        AND up.success_rate >= %s
                        AND up.last_seen < %s
                        ORDER BY up.last_seen ASC, RANDOM()
                        LIMIT 3
                    """, (user_language_id, current_difficulty, 80,
                          datetime.now() - interval_due))
                    review_words = cur.fetchall()
                    review_words = review_words[:3]  # Максимум 3 Review
                    main_bucket.extend(review_words[:max(0, 3 - len(main_bucket))])
                    if len(review_words) < 1:
                        logger.warning("No Review words found")

                    # New-L: repeats=0, учитываем карантин и паузу
                    new_limit = 3 - new_words_count
                    if block_new_words:
                        new_limit = 0
                    if new_limit > 0:
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
                        """, (target_language_id, current_difficulty, user_language_id,
                              user_language_id, datetime.now() - timedelta(minutes=CONFIG["NEW_WORD_PAUSE_MINUTES"]),
                              new_limit))
                        new_words = cur.fetchall()
                        main_bucket.extend(new_words[:max(0, 3 - len(main_bucket))])
                        new_words_count += len(new_words)
                        if len(new_words) < 1 and not block_new_words:
                            logger.warning("No New-L words found")

                    # Дозаполняем Main-bucket до 7
                    while len(main_bucket) < 7:
                        # Пробуем Weak, Review, New-L снова с мягкими ограничениями
                        cur.execute("""
                            SELECT w.id, w.text
                            FROM words w
                            JOIN user_progress up ON w.id = up.word_id
                            WHERE up.user_language_id = %s
                            AND w.difficulty = %s
                            AND up.last_seen < %s
                            ORDER BY RANDOM()
                            LIMIT %s
                        """, (user_language_id, current_difficulty,
                              datetime.now() - timedelta(minutes=CONFIG["QUARANTINE_MINUTES"]),
                              7 - len(main_bucket)))
                        extra_words = cur.fetchall()
                        main_bucket.extend(extra_words)
                        if len(extra_words) == 0:
                            logger.warning("Insufficient words for Main-bucket, trying fallback")
                            cur.execute("""
                                SELECT id, text
                                FROM words
                                WHERE language_id = %s AND difficulty = %s
                                ORDER BY RANDOM()
                                LIMIT %s
                            """, (target_language_id, current_difficulty, 7 - len(main_bucket)))
                            main_bucket.extend(cur.fetchall())
                        if len(main_bucket) < 7:
                            logger.error(f"Cannot fill Main-bucket: {len(main_bucket)} words")
                            break

                    words.extend(main_bucket[:7])

                    # 2. Stretch+1 (1 слово, уровень +1)
                    if stretch_difficulty:
                        cur.execute("""
                            SELECT id, text
                            FROM words
                            WHERE language_id = %s
                            AND difficulty = %s
                            AND frequency_rank = 1
                            AND (id NOT IN (
                                SELECT word_id FROM user_progress
                                WHERE user_language_id = %s
                                AND last_seen > %s
                            ) OR TRUE)
                            ORDER BY RANDOM()
                            LIMIT 1
                        """, (target_language_id, stretch_difficulty, user_language_id,
                              datetime.now() - timedelta(minutes=CONFIG["QUARANTINE_MINUTES"])))
                        stretch_word = cur.fetchone()
                        if stretch_word:
                            words.append(stretch_word)
                        else:
                            logger.warning("No Stretch+1 word found, adding to Main-bucket")
                            words.extend(main_bucket[7:8])
                    else:
                        words.extend(main_bucket[7:8])

                    # 3. Patch-1 (1 слово, уровень -1)
                    if patch_difficulty:
                        cur.execute("""
                            SELECT id, text
                            FROM words
                            WHERE language_id = %s
                            AND difficulty = %s
                            AND frequency_rank = 3
                            AND (id NOT IN (
                                SELECT word_id FROM user_progress
                                WHERE user_language_id = %s
                                AND last_seen > %s
                            ) OR TRUE)
                            ORDER BY RANDOM()
                            LIMIT 1
                        """, (target_language_id, patch_difficulty, user_language_id,
                              datetime.now() - timedelta(minutes=CONFIG["QUARANTINE_MINUTES"])))
                        patch_word = cur.fetchone()
                        if patch_word:
                            words.append(patch_word)
                        else:
                            logger.warning("No Patch-1 word found, adding to Main-bucket")
                            words.extend(main_bucket[8:9])
                    else:
                        words.extend(main_bucket[8:9])

                    # 4. Adaptive (1 слово)
                    if weak_words:
                        # Есть Weak, берём ещё одно
                        words.append(weak_words[0])
                    elif recent_success_rate >= CONFIG["ADAPTIVE_SUCCESS_THRESHOLD"] and stretch_difficulty:
                        # Высокий успех, второе Stretch+1
                        cur.execute("""
                            SELECT id, text
                            FROM words
                            WHERE language_id = %s
                            AND difficulty = %s
                            AND frequency_rank = 1
                            AND (id NOT IN (
                                SELECT word_id FROM user_progress
                                WHERE user_language_id = %s
                                AND last_seen > %s
                            ) OR TRUE)
                            ORDER BY RANDOM()
                            LIMIT 1
                        """, (target_language_id, stretch_difficulty, user_language_id,
                              datetime.now() - timedelta(minutes=CONFIG["QUARANTINE_MINUTES"])))
                        adaptive_word = cur.fetchone()
                        if adaptive_word:
                            words.append(adaptive_word)
                        else:
                            words.extend(main_bucket[9:10])
                    else:
                        # Patch-1 или New-L (с учётом лимита)
                        if new_words_count < CONFIG["MAX_NEW_WORDS"] and not block_new_words:
                            cur.execute("""
                                SELECT id, text
                                FROM words
                                WHERE language_id = %s
                                AND difficulty = %s
                                AND id NOT IN (
                                    SELECT word_id FROM user_progress WHERE user_language_id = %s
                                )
                                AND (id NOT IN (
                                    SELECT word_id FROM user_progress
                                    WHERE user_language_id = %s
                                    AND last_seen > %s
                                ) OR TRUE)
                                ORDER BY frequency_rank ASC, RANDOM()
                                LIMIT 1
                            """, (target_language_id, current_difficulty, user_language_id,
                                  user_language_id, datetime.now() - timedelta(minutes=CONFIG["NEW_WORD_PAUSE_MINUTES"])))
                            adaptive_word = cur.fetchone()
                            if adaptive_word:
                                words.append(adaptive_word)
                                new_words_count += 1
                            else:
                                words.extend(main_bucket[9:10])
                        else:
                            # Patch-1
                            if patch_difficulty:
                                cur.execute("""
                                    SELECT id, text
                                    FROM words
                                    WHERE language_id = %s
                                    AND difficulty = %s
                                    AND frequency_rank = 3
                                    AND (id NOT IN (
                                        SELECT word_id FROM user_progress
                                        WHERE user_language_id = %s
                                        AND last_seen > %s
                                    ) OR TRUE)
                                    ORDER BY RANDOM()
                                    LIMIT 1
                                """, (target_language_id, patch_difficulty, user_language_id,
                                      datetime.now() - timedelta(minutes=CONFIG["QUARANTINE_MINUTES"])))
                                adaptive_word = cur.fetchone()
                                if adaptive_word:
                                    words.append(adaptive_word)
                                else:
                                    words.extend(main_bucket[9:10])
                            else:
                                words.extend(main_bucket[9:10])

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
        
        # Проверяем финальный размер
        if len(result) < CONFIG["SESSION_SIZE"]:
            logger.error(f"Final result: {len(result)} words, expected {CONFIG['SESSION_SIZE']}")
            raise ValueError(f"Insufficient valid words: {len(result)}")

        logger.info(f"Selected {len(result)} words for user {user_id}")
        return result
    
    except Exception as e:
        logger.error(f"Error in select_words: {e}")
        raise