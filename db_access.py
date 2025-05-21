# db_access.py
# Управляет подключением к PostgreSQL, выполняет SQL-запросы и транзакции.
# Предоставляет функции для работы с таблицами: words, word_senses, user_progress, user_languages, users.
# Соответствует спецификации MVP v1, раздел 8.1.

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Параметры подключения к базе данных
DB_PARAMS = {
    "dbname": "lng_app",
    "user": "borvel",
    "password": "",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    """Создаёт и возвращает соединение с PostgreSQL."""
    try:
        conn = psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

def close_db_connection(conn):
    """Закрывает соединение с базой данных."""
    if conn:
        conn.close()

def get_or_create_user(username):
    """Возвращает или создаёт пользователя, возвращает user_id."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (username, base_language_id, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
                    RETURNING id
                """, (username, 2, datetime.now()))  # base_language_id=2 (русский)
                user_id = cur.fetchone()['id']
        return user_id
    except psycopg2.Error as e:
        logger.error(f"Error in get_or_create_user: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_or_create_user_language(user_id, target_language_id):
    """Возвращает или создаёт запись в user_languages, возвращает (user_language_id, level)."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, level FROM user_languages
                    WHERE user_id = %s AND target_language_id = %s AND is_active = TRUE
                """, (user_id, target_language_id))
                result = cur.fetchone()
                if result:
                    return result['id'], result['level']
                
                # Создаём новую запись
                cur.execute("""
                    INSERT INTO user_languages (user_id, target_language_id, level, is_active, started_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, level
                """, (user_id, target_language_id, 'A2', True, datetime.now()))
                result = cur.fetchone()
                return result['id'], result['level']
    except psycopg2.Error as e:
        logger.error(f"Error in get_or_create_user_language: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_user_last_active(user_id):
    """Возвращает дату последнего входа пользователя или None."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT last_active FROM users WHERE id = %s
                """, (user_id,))
                result = cur.fetchone()
                return result['last_active'] if result else None
    except psycopg2.Error as e:
        logger.error(f"Error in get_user_last_active: {e}")
        raise
    finally:
        close_db_connection(conn)

def update_user_last_active(user_id):
    """Обновляет last_active пользователя до текущего времени."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users SET last_active = %s WHERE id = %s
                """, (datetime.now(), user_id))
    except psycopg2.Error as e:
        logger.error(f"Error in update_user_last_active: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_session_count(user_language_id):
    """Возвращает количество завершённых сессий для user_language_id."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count FROM user_progress
                    WHERE user_language_id = %s
                    GROUP BY session_id
                """, (user_language_id,))
                result = cur.fetchone()
                return result['count'] if result else 0
    except psycopg2.Error as e:
        logger.error(f"Error in get_session_count: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_words_for_onboarding(session_number, user_language_id):
    """Возвращает слова для онбординга (сессии 1 и 2)."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                if session_number == 1:
                    # Сессия 1: 5 A1 (frequency_rank=1) + 5 A2 (new)
                    cur.execute("""
                        SELECT id, text FROM words
                        WHERE language_id = 1 AND difficulty = 1 AND frequency_rank = 1
                        ORDER BY RANDOM() LIMIT 5
                    """)
                    a1_words = cur.fetchall()
                    cur.execute("""
                        SELECT id, text FROM words
                        WHERE language_id = 1 AND difficulty = 2
                        AND id NOT IN (
                            SELECT word_id FROM user_progress WHERE user_language_id = %s
                        )
                        ORDER BY RANDOM() LIMIT 5
                    """, (user_language_id,))
                    a2_words = cur.fetchall()
                    return a1_words + a2_words
                
                elif session_number == 2:
                    # Сессия 2: 3–4 слова из сессии 1 + 3–4 новых A2 + 0–2 A1
                    cur.execute("""
                        SELECT w.id, w.text FROM words w
                        JOIN user_progress up ON w.id = up.word_id
                        WHERE up.user_language_id = %s
                        ORDER BY RANDOM() LIMIT 4
                    """, (user_language_id,))
                    prev_words = cur.fetchall()
                    new_limit = 4 if len(prev_words) == 3 else 3
                    cur.execute("""
                        SELECT id, text FROM words
                        WHERE language_id = 1 AND difficulty = 2
                        AND id NOT IN (
                            SELECT word_id FROM user_progress WHERE user_language_id = %s
                        )
                        ORDER BY RANDOM() LIMIT %s
                    """, (user_language_id, new_limit))
                    new_a2_words = cur.fetchall()
                    remaining = 10 - (len(prev_words) + len(new_a2_words))
                    if remaining > 0:
                        cur.execute("""
                            SELECT id, text FROM words
                            WHERE language_id = 1 AND difficulty = 1 AND frequency_rank = 1
                            AND id NOT IN (
                                SELECT word_id FROM user_progress WHERE user_language_id = %s
                            )
                            ORDER BY RANDOM() LIMIT %s
                        """, (user_language_id, remaining))
                        a1_words = cur.fetchall()
                        return prev_words + new_a2_words + a1_words
                    return prev_words + new_a2_words
    except psycopg2.Error as e:
        logger.error(f"Error in get_words_for_onboarding: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_word_translation(word_id, translation_language_id=2):
    """Возвращает перевод слова для указанного языка."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT translation FROM word_senses
                    WHERE word_id = %s AND language_id = %s LIMIT 1
                """, (word_id, translation_language_id))
                result = cur.fetchone()
                return result['translation'] if result else None
    except psycopg2.Error as e:
        logger.error(f"Error in get_word_translation: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_wrong_translation(word_id, translation_language_id=2):
    """Возвращает случайный неправильный перевод."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT translation FROM word_senses
                    WHERE language_id = %s AND word_id != %s
                    ORDER BY RANDOM() LIMIT 1
                """, (translation_language_id, word_id))
                result = cur.fetchone()
                return result['translation'] if result else None
    except psycopg2.Error as e:
        logger.error(f"Error in get_wrong_translation: {e}")
        raise
    finally:
        close_db_connection(conn)

def update_user_progress(user_language_id, word_id, is_correct, session_id):
    """Обновляет прогресс пользователя для слова, добавляет last_answer_wrong."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT repeats, successes FROM user_progress
                    WHERE user_language_id = %s AND word_id = %s
                """, (user_language_id, word_id))
                result = cur.fetchone()
                
                if result:
                    repeats = result['repeats'] + 1
                    successes = result['successes'] + 1 if is_correct else result['successes']
                    success_rate = (successes / repeats) * 100
                    cur.execute("""
                        UPDATE user_progress
                        SET repeats = %s, successes = %s, success_rate = %s,
                            last_seen = %s, last_answer_wrong = %s, session_id = %s
                        WHERE user_language_id = %s AND word_id = %s
                    """, (repeats, successes, success_rate, datetime.now(),
                          not is_correct, session_id, user_language_id, word_id))
                else:
                    repeats = 1
                    successes = 1 if is_correct else 0
                    success_rate = 100 if is_correct else 0
                    cur.execute("""
                        INSERT INTO user_progress (user_language_id, word_id, repeats, successes,
                            success_rate, last_seen, last_answer_wrong, session_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (user_language_id, word_id, repeats, successes, success_rate,
                          datetime.now(), not is_correct, session_id))
    except psycopg2.Error as e:
        logger.error(f"Error in update_user_progress: {e}")
        raise
    finally:
        close_db_connection(conn)

def set_user_level(user_language_id, new_level):
    """Обновляет уровень пользователя."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE user_languages SET level = %s WHERE id = %s
                """, (new_level, user_language_id))
    except psycopg2.Error as e:
        logger.error(f"Error in set_user_level: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_recent_success_rate(user_language_id, num_answers=20):
    """Возвращает success_rate за последние num_answers ответов."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT successes, repeats FROM user_progress
                    WHERE user_language_id = %s
                    ORDER BY last_seen DESC LIMIT %s
                """, (user_language_id, num_answers))
                results = cur.fetchall()
                if not results:
                    return 0
                total_successes = sum(r['successes'] for r in results)
                total_repeats = sum(r['repeats'] for r in results)
                return (total_successes / total_repeats * 100) if total_repeats > 0 else 0
    except psycopg2.Error as e:
        logger.error(f"Error in get_recent_success_rate: {e}")
        raise
    finally:
        close_db_connection(conn)

def get_session_success_rates(user_language_id, num_sessions=3):
    """Возвращает success_rate для последних num_sessions сессий."""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT session_id, SUM(successes) as successes, SUM(repeats) as repeats
                    FROM user_progress
                    WHERE user_language_id = %s
                    GROUP BY session_id
                    ORDER BY MAX(last_seen) DESC LIMIT %s
                """, (user_language_id, num_sessions))
                sessions = cur.fetchall()
                return [
                    (s['successes'] / s['repeats'] * 100) if s['repeats'] > 0 else 0
                    for s in sessions
                ]
    except psycopg2.Error as e:
        logger.error(f"Error in get_session_success_rates: {e}")
        raise
    finally:
        close_db_connection(conn)