# onboarding.py
# Формирует слова для первых двух сессий новичков (онбординг).
# Сессия 1: 5 A1 (frequency_rank=1) + 5 новых A2.
# Сессия 2: 3–4 слова из сессии 1 + 3–4 новых A2 + 0–2 A1.
# Соответствует спецификации MVP v1, раздел 4.

import random
import logging
from db_access import (
    get_session_count, get_words_for_onboarding,
    get_word_translation, get_wrong_translation
)
from config import CONFIG

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_new_user(user_language_id):
    """Проверяет, является ли пользователь новичком (менее 10 слов в прогрессе)."""
    try:
        session_count = get_session_count(user_language_id)
        # Новичок: менее 1 полной сессии (10 слов)
        return session_count < 1
    except Exception as e:
        logger.error(f"Error in is_new_user: {e}")
        raise

def get_session_number(user_language_id):
    """Возвращает номер текущей сессии (1 или 2) для онбординга."""
    try:
        session_count = get_session_count(user_language_id)
        if session_count == 0:
            return 1  # Первая сессия
        elif session_count == 1:
            return 2  # Вторая сессия
        return None  # Не онбординг
    except Exception as e:
        logger.error(f"Error in get_session_number: {e}")
        raise

def select_onboarding_words(user_id, target_language_id, user_language_id, translation_language_id=2):
    """Выбирает 10 слов для онбординга, возвращает список с переводами."""
    try:
        # Проверяем, новичок ли пользователь
        if not is_new_user(user_language_id):
            logger.info(f"User {user_id} is not a newbie, skipping onboarding")
            return None

        # Определяем номер сессии
        session_number = get_session_number(user_language_id)
        if not session_number:
            logger.info(f"User {user_id} has completed onboarding")
            return None

        logger.info(f"Selecting onboarding words for session {session_number}, user {user_id}")

        # Получаем слова из базы
        words = get_words_for_onboarding(session_number, user_language_id)
        
        # Проверяем, достаточно ли слов
        if len(words) < CONFIG["SESSION_SIZE"]:
            logger.warning(f"Only {len(words)} words found for onboarding session {session_number}")
            # Можно добавить резервные слова A1, но для MVP кидаем ошибку
            raise ValueError(f"Insufficient words for onboarding: {len(words)}")

        # Формируем результат с переводами
        result = []
        for word in words:
            word_id = word['id']
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

        # Перемешиваем слова, как указано в спецификации
        random.shuffle(result)
        
        # Проверяем финальный размер
        if len(result) < CONFIG["SESSION_SIZE"]:
            logger.warning(f"Final onboarding result: {len(result)} words, expected {CONFIG['SESSION_SIZE']}")
            raise ValueError(f"Insufficient valid words after translation: {len(result)}")

        logger.info(f"Onboarding session {session_number} for user {user_id}: {len(result)} words selected")
        return result[:CONFIG["SESSION_SIZE"]]
    
    except Exception as e:
        logger.error(f"Error in select_onboarding_words: {e}")
        raise