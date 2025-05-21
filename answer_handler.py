# answer_handler.py
# Обрабатывает ответы пользователя, обновляет статистику в user_progress.
# Соответствует спецификации MVP v1, раздел 5.

import logging
from db_access import update_user_progress

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_answer(user_language_id, word_id, is_correct, session_id):
    """Обрабатывает ответ пользователя и обновляет user_progress."""
    try:
        logger.info(f"Handling answer for user_language_id {user_language_id}, word_id {word_id}, is_correct {is_correct}")

        # Проверяем входные данные
        if not all([user_language_id, word_id, session_id is not None]):
            logger.error("Invalid input: user_language_id, word_id, or session_id is missing")
            raise ValueError("Invalid input parameters")

        # Обновляем прогресс в базе
        update_user_progress(user_language_id, word_id, is_correct, session_id)
        
        logger.info(f"Answer processed: word_id {word_id}, is_correct {is_correct}")
        return True
    
    except Exception as e:
        logger.error(f"Error in handle_answer: {e}")
        raise