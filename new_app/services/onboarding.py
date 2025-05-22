import random
import logging
from typing import List, Dict, Any, Optional
from psycopg2.extras import RealDictCursor
from db.database import (
    get_db_connection, close_db_connection, get_word_translation, 
    get_wrong_translation
)
from models.config import CONFIG, LEVEL_TO_DIFFICULTY

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def select_onboarding_words(user_id: int, target_language_id: int, user_language_id: int, 
                            translation_language_id: int = 2) -> List[Dict[str, Any]]:
    """
    Выбирает слова для онбординга новых пользователей (первые 1-2 сессии).
    Возвращает None, если пользователь уже имеет историю ответов.
    """
    try:
        # Проверяем, новый ли пользователь
        conn = get_db_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM user_progress WHERE user_language_id = %s
                    """, (user_language_id,))
                    result = cur.fetchone()
                    answers_count = result['count'] if result else 0
                    
                    # Определяем номер сессии
                    if answers_count == 0:
                        session_num = 1
                    elif answers_count < CONFIG["SESSION_SIZE"]:
                        session_num = 2
                    else:
                        # Пользователь уже не новичок
                        return None
                    
                    logger.info(f"Onboarding session {session_num} for user {user_id}")
                    
                    # Первая сессия: 5 частотных A1 + 5 новых A2
                    if session_num == 1:
                        return _first_session_words(
                            conn, user_language_id, target_language_id, translation_language_id
                        )
                    
                    # Вторая сессия: 3-4 слова из сессии-1 + 3-4 новых A2 + 0-2 легких A1
                    else:
                        return _second_session_words(
                            conn, user_language_id, target_language_id, translation_language_id
                        )
        finally:
            if conn:
                close_db_connection(conn)
    except Exception as e:
        logger.error(f"Error in select_onboarding_words: {e}")
        return None

def _first_session_words(conn, user_language_id: int, target_language_id: int, 
                         translation_language_id: int) -> List[Dict[str, Any]]:
    """Подбирает слова для первой сессии."""
    try:
        with conn.cursor() as cur:
            # Выбираем 5 частотных A1
            cur.execute("""
                SELECT w.id, w.text 
                FROM words w
                WHERE w.difficulty = 1  -- A1
                AND w.language_id = %s
                ORDER BY frequency_rank ASC NULLS LAST, RANDOM()
                LIMIT 5
            """, (target_language_id,))
            a1_words = cur.fetchall()
            
            # Выбираем 5 новых A2
            cur.execute("""
                SELECT w.id, w.text 
                FROM words w
                WHERE w.difficulty = 2  -- A2
                AND w.language_id = %s
                ORDER BY RANDOM()
                LIMIT 5
            """, (target_language_id,))
            a2_words = cur.fetchall()
            
            # Объединяем результаты
            words = a1_words + a2_words
            random.shuffle(words)
            
            # Проверяем, что у нас ровно 10 слов, иначе дополняем случайными словами
            if len(words) < CONFIG["SESSION_SIZE"]:
                missing_count = CONFIG["SESSION_SIZE"] - len(words)
                logger.warning(f"Not enough words for first session, need {missing_count} more")
                
                # Получаем ID уже выбранных слов
                selected_ids = [w['id'] for w in words]
                
                # Выбираем дополнительные слова
                cur.execute("""
                    SELECT w.id, w.text 
                    FROM words w
                    WHERE w.id NOT IN (SELECT unnest(%s::int[]))
                    AND w.language_id = %s
                    ORDER BY RANDOM()
                    LIMIT %s
                """, (selected_ids, target_language_id, missing_count))
                additional_words = cur.fetchall()
                words.extend(additional_words)
                
            # Если слов получилось больше 10, обрезаем
            if len(words) > CONFIG["SESSION_SIZE"]:
                logger.warning(f"Too many words for first session: {len(words)}, trimming to {CONFIG['SESSION_SIZE']}")
                words = words[:CONFIG["SESSION_SIZE"]]
            
            # Добавляем переводы и варианты ответов
            words_with_options = []
            for word in words:
                correct_translation = get_word_translation(word['id'], translation_language_id)
                if not correct_translation:
                    logger.warning(f"No translation found for word {word['id']}, skipping")
                    continue
                
                # Определяем сложность для неправильных вариантов
                difficulty = 1 if word['id'] in [w['id'] for w in a1_words] else 2
                
                # Получаем неправильные варианты
                wrong_translations = get_wrong_translation(
                    word['id'], difficulty, translation_language_id, 3
                )
                
                # Собираем все варианты
                options = [correct_translation] + wrong_translations
                random.shuffle(options)
                
                words_with_options.append({
                    'wordId': word['id'],
                    'text': word['text'],
                    'correctTranslation': correct_translation,
                    'options': options
                })
            
            # Финальная проверка на количество слов
            if len(words_with_options) != CONFIG["SESSION_SIZE"]:
                logger.warning(f"Final word count for first session is {len(words_with_options)}, expected {CONFIG['SESSION_SIZE']}")
                # Если не хватает слов с переводами, дублируем существующие
                while len(words_with_options) < CONFIG["SESSION_SIZE"] and len(words_with_options) > 0:
                    clone = words_with_options[0].copy()
                    words_with_options.append(clone)
                
                # Если слов больше 10, обрезаем
                if len(words_with_options) > CONFIG["SESSION_SIZE"]:
                    words_with_options = words_with_options[:CONFIG["SESSION_SIZE"]]
            
            logger.info(f"First session word count: {len(words_with_options)}")
            return words_with_options
    
    except Exception as e:
        logger.error(f"Error in _first_session_words: {e}")
        return []

def _second_session_words(conn, user_language_id: int, target_language_id: int, 
                          translation_language_id: int) -> List[Dict[str, Any]]:
    """Подбирает слова для второй сессии."""
    try:
        with conn.cursor() as cur:
            # Получаем слова из первой сессии
            cur.execute("""
                SELECT DISTINCT w.id, w.text
                FROM words w
                JOIN user_progress up ON w.id = up.word_id
                WHERE up.user_language_id = %s
                ORDER BY up.last_seen DESC
                LIMIT 10
            """, (user_language_id,))
            previous_words = cur.fetchall()
            
            # Выбираем 3-4 слова из первой сессии для повторения
            review_count = random.randint(3, 4)
            review_words = random.sample(previous_words, min(review_count, len(previous_words)))
            review_word_ids = [w['id'] for w in review_words]
            
            # Выбираем 3-4 новых A2
            cur.execute("""
                SELECT w.id, w.text 
                FROM words w
                WHERE w.difficulty = 2  -- A2
                AND w.language_id = %s
                AND w.id NOT IN (SELECT unnest(%s::int[]))
                ORDER BY RANDOM()
                LIMIT %s
            """, (target_language_id, review_word_ids, 4))
            new_a2_words = cur.fetchall()
            
            # Объединяем результаты
            words = review_words + new_a2_words
            
            # Если не хватает до 10 слов, добавляем легкие A1
            if len(words) < CONFIG["SESSION_SIZE"]:
                remaining = CONFIG["SESSION_SIZE"] - len(words)
                cur.execute("""
                    SELECT w.id, w.text 
                    FROM words w
                    WHERE w.difficulty = 1  -- A1
                    AND w.language_id = %s
                    AND w.id NOT IN (SELECT unnest(%s::int[]))
                    ORDER BY frequency_rank ASC NULLS LAST, RANDOM()
                    LIMIT %s
                """, (
                    target_language_id, 
                    [w['id'] for w in words], 
                    remaining
                ))
                a1_words = cur.fetchall()
                words.extend(a1_words)
            
            # Если всё еще не хватает слов, добавляем случайные слова
            if len(words) < CONFIG["SESSION_SIZE"]:
                missing_count = CONFIG["SESSION_SIZE"] - len(words)
                logger.warning(f"Not enough words for second session, need {missing_count} more")
                
                # Получаем ID уже выбранных слов
                selected_ids = [w['id'] for w in words]
                
                # Выбираем любые дополнительные слова
                cur.execute("""
                    SELECT w.id, w.text 
                    FROM words w
                    WHERE w.id NOT IN (SELECT unnest(%s::int[]))
                    AND w.language_id = %s
                    ORDER BY RANDOM()
                    LIMIT %s
                """, (selected_ids, target_language_id, missing_count))
                additional_words = cur.fetchall()
                words.extend(additional_words)
            
            # Если слов больше 10, обрезаем
            if len(words) > CONFIG["SESSION_SIZE"]:
                logger.warning(f"Too many words for second session: {len(words)}, trimming to {CONFIG['SESSION_SIZE']}")
                words = words[:CONFIG["SESSION_SIZE"]]
            
            # Перемешиваем слова
            random.shuffle(words)
            
            # Добавляем переводы и варианты ответов
            words_with_options = []
            for word in words:
                correct_translation = get_word_translation(word['id'], translation_language_id)
                if not correct_translation:
                    logger.warning(f"No translation found for word {word['id']}, skipping")
                    continue
                
                # Определяем сложность для неправильных вариантов
                cur.execute("""
                    SELECT difficulty FROM words WHERE id = %s
                """, (word['id'],))
                result = cur.fetchone()
                difficulty = result['difficulty'] if result else 1
                
                # Получаем неправильные варианты
                wrong_translations = get_wrong_translation(
                    word['id'], difficulty, translation_language_id, 3
                )
                
                # Собираем все варианты
                options = [correct_translation] + wrong_translations
                random.shuffle(options)
                
                words_with_options.append({
                    'wordId': word['id'],
                    'text': word['text'],
                    'correctTranslation': correct_translation,
                    'options': options
                })
            
            # Финальная проверка на количество слов
            if len(words_with_options) != CONFIG["SESSION_SIZE"]:
                logger.warning(f"Final word count for second session is {len(words_with_options)}, expected {CONFIG['SESSION_SIZE']}")
                # Если не хватает слов с переводами, дублируем существующие
                while len(words_with_options) < CONFIG["SESSION_SIZE"] and len(words_with_options) > 0:
                    clone = words_with_options[0].copy()
                    words_with_options.append(clone)
                
                # Если слов больше 10, обрезаем
                if len(words_with_options) > CONFIG["SESSION_SIZE"]:
                    words_with_options = words_with_options[:CONFIG["SESSION_SIZE"]]
            
            logger.info(f"Second session word count: {len(words_with_options)}")
            return words_with_options
    
    except Exception as e:
        logger.error(f"Error in _second_session_words: {e}")
        return [] 