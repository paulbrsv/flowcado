import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Any
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Параметры подключения к базе данных из оригинального приложения
DB_PARAMS = {
    "dbname": "lng_app",
    "user": "borvel",
    "password": "",
    "host": "localhost",
    "port": "5432"
}

# Строка подключения
DATABASE_URL = os.environ.get("DATABASE_URL", f"postgresql://{DB_PARAMS['user']}:{DB_PARAMS['password']}@{DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_PARAMS['dbname']}")

def get_db_connection():
    """Возвращает соединение с базой данных."""
    try:
        conn = psycopg2.connect(**DB_PARAMS, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        raise

def close_db_connection(conn):
    """Закрывает соединение с БД."""
    if conn:
        conn.close()

def get_db_session():
    """Генератор для сессии БД с автоматическим закрытием соединения."""
    conn = None
    try:
        conn = get_db_connection()
        yield conn
    finally:
        if conn:
            close_db_connection(conn)

# Функции для работы с пользователями
def get_or_create_user(username: str) -> int:
    """Возвращает ID существующего пользователя или создает нового."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                # Создаём или получаем существующего пользователя
                cur.execute("""
                    INSERT INTO users (username, base_language_id, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
                    RETURNING id
                """, (username, 2, datetime.now()))  # base_language_id=2 (русский)
                user_id = cur.fetchone()['id']
                return user_id
    except Exception as e:
        logger.error(f"Ошибка получения/создания пользователя: {e}")
        raise
    finally:
        if conn:
            close_db_connection(conn)

def get_or_create_user_language(user_id: int, target_language_id: int) -> tuple:
    """Возвращает ID связи пользователь-язык и уровень."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                # Ищем связь
                cur.execute("""
                    SELECT id, level FROM user_languages
                    WHERE user_id = %s AND target_language_id = %s AND is_active = TRUE
                """, (user_id, target_language_id))
                result = cur.fetchone()
                
                if result:
                    return result['id'], result['level']
                
                # Создаем новую связь с начальным уровнем A2
                cur.execute("""
                    INSERT INTO user_languages (user_id, target_language_id, level, is_active, started_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, level
                """, (user_id, target_language_id, 'A2', True, datetime.now()))
                result = cur.fetchone()
                return result['id'], result['level']
    except Exception as e:
        logger.error(f"Ошибка получения/создания user_language: {e}")
        raise
    finally:
        if conn:
            close_db_connection(conn)

def update_user_last_active(user_id: int) -> None:
    """Обновляет время последней активности пользователя."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users SET last_active = %s WHERE id = %s
                """, (datetime.now(), user_id))
    except Exception as e:
        logger.error(f"Ошибка обновления last_active: {e}")
        raise
    finally:
        if conn:
            close_db_connection(conn)

def update_user_progress(user_language_id: int, word_id: int, is_correct: bool, session_id: str) -> None:
    """Обновляет прогресс пользователя для заданного слова."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                # Проверяем наличие записи
                cur.execute("""
                    SELECT repeats, successes FROM user_progress
                    WHERE user_language_id = %s AND word_id = %s
                """, (user_language_id, word_id))
                result = cur.fetchone()
                
                if result:
                    # Обновляем существующую запись
                    repeats = result['repeats'] + 1
                    successes = result['successes'] + (1 if is_correct else 0)
                    success_rate = successes / repeats
                    
                    cur.execute("""
                        UPDATE user_progress
                        SET repeats = %s, 
                            successes = %s, 
                            success_rate = %s, 
                            last_seen = %s,
                            last_answer_wrong = %s,
                            session_id = %s
                        WHERE user_language_id = %s AND word_id = %s
                    """, (
                        repeats, successes, success_rate, 
                        datetime.now(), not is_correct, session_id,
                        user_language_id, word_id
                    ))
                else:
                    # Создаем новую запись
                    successes = 1 if is_correct else 0
                    repeats = 1
                    success_rate = successes / repeats
                    
                    cur.execute("""
                        INSERT INTO user_progress 
                        (user_language_id, word_id, repeats, successes, success_rate, 
                         last_seen, last_answer_wrong, session_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_language_id, word_id, repeats, successes, success_rate,
                        datetime.now(), not is_correct, session_id
                    ))
    except Exception as e:
        logger.error(f"Ошибка обновления прогресса пользователя: {e}")
        raise
    finally:
        if conn:
            close_db_connection(conn)

def get_recent_success_rate(user_language_id: int, num_answers: int = 20) -> float:
    """Возвращает среднюю успеваемость за последние num_answers ответов."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT AVG(CASE WHEN last_answer_wrong THEN 0 ELSE 1 END) * 100 as avg_success
                    FROM (
                        SELECT last_answer_wrong
                        FROM user_progress
                        WHERE user_language_id = %s
                        ORDER BY last_seen DESC
                        LIMIT %s
                    ) as recent_answers
                """, (user_language_id, num_answers))
                result = cur.fetchone()
                return result['avg_success'] if result and result['avg_success'] is not None else 50.0
    except Exception as e:
        logger.error(f"Ошибка расчета recent_success_rate: {e}")
        return 50.0  # Значение по умолчанию
    finally:
        if conn:
            close_db_connection(conn)

# Функции для работы со словами и переводами
def get_word_translation(word_id: int, translation_language_id: int = 2) -> str:
    """Возвращает перевод слова на указанный язык."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT translation FROM word_senses
                    WHERE word_id = %s AND language_id = %s
                    LIMIT 1
                """, (word_id, translation_language_id))
                result = cur.fetchone()
                return result['translation'] if result else ""
    except Exception as e:
        logger.error(f"Ошибка получения перевода слова: {e}")
        return ""
    finally:
        if conn:
            close_db_connection(conn)

def get_wrong_translation(correct_word_id: int, difficulty: int, translation_language_id: int = 2, count: int = 3) -> List[str]:
    """Возвращает список из count неправильных переводов подходящего уровня сложности."""
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ws.translation
                    FROM word_senses ws
                    JOIN words w ON ws.word_id = w.id
                    WHERE ws.language_id = %s
                    AND w.difficulty = %s
                    AND w.id != %s
                    ORDER BY RANDOM()
                    LIMIT %s
                """, (translation_language_id, difficulty, correct_word_id, count))
                return [row['translation'] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка получения неправильных переводов: {e}")
        return []
    finally:
        if conn:
            close_db_connection(conn) 