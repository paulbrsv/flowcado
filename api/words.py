from fastapi import APIRouter, HTTPException, Depends, status, Request, Response, Cookie, Form
from typing import Optional, List, Dict, Any
import uuid
import logging

from db.database import (
    get_db_connection, close_db_connection, get_or_create_user,
    get_or_create_user_language, update_user_progress
)
from services.picker import select_words
from services.onboarding import select_onboarding_words
from services.session_evaluator import SessionEvaluator
from models.schemas import WordSession, UserAnswer, AnswerResult, SessionComplete, SessionResult
from models.messages import ERROR_MESSAGES, SUCCESS_MESSAGES, RESULT_MESSAGES

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
evaluator = SessionEvaluator()

# Значения по умолчанию
DEFAULT_TARGET_LANGUAGE_ID = 3  # сербский
DEFAULT_TRANSLATION_LANGUAGE_ID = 2  # русский

@router.get("/start-session", response_model=WordSession)
async def start_session(
    user_id: Optional[str] = Cookie(None),
    username: Optional[str] = Cookie(None),
    target_language_id: int = DEFAULT_TARGET_LANGUAGE_ID,
    translation_language_id: int = DEFAULT_TRANSLATION_LANGUAGE_ID
):
    """Запускает новую сессию изучения слов."""
    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES["unauthorized"]
        )

    try:
        user_id = int(user_id)

        # Получаем или создаем связь пользователь-язык
        user_language_id, level = get_or_create_user_language(user_id, target_language_id)

        # Сначала пробуем онбординг для новых пользователей
        words = select_onboarding_words(
            user_id, target_language_id, user_language_id, translation_language_id
        )

        # Если пользователь не новый, используем основной подбор слов
        if not words:
            words = select_words(
                user_id, target_language_id, user_language_id, level, translation_language_id
            )

        if not words or len(words) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES["insufficient_words"]
            )

        # Создаем ID сессии
        session_id = str(uuid.uuid4())

        # Сервисный метод для логирования
        logger.info(f"Started session {session_id} for user {user_id}, level {level}")

        return WordSession(
            sessionId=session_id,
            words=words,
            totalWords=len(words)
        )

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES["general_error"]
        )

@router.post("/submit-answer", response_model=AnswerResult)
async def submit_answer(
    answer: UserAnswer,
    user_id: Optional[str] = Cookie(None),
    username: Optional[str] = Cookie(None),
    target_language_id: int = DEFAULT_TARGET_LANGUAGE_ID
):
    """Проверяет ответ пользователя."""
    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES["unauthorized"]
        )

    try:
        user_id = int(user_id)

        # Проверяем наличие ответа
        if not answer.userAnswer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES["no_answer"]
            )

        # Проверяем правильность ответа
        is_correct = answer.userAnswer == answer.correctTranslation

        # Получаем связь пользователь-язык
        user_language_id, level = get_or_create_user_language(user_id, target_language_id)

        # Обновляем прогресс
        update_user_progress(user_language_id, answer.wordId, is_correct, answer.sessionId)

        # Формируем текст сообщения
        message = ""
        if is_correct:
            message = SUCCESS_MESSAGES["correct_answer"]
        else:
            message = RESULT_MESSAGES["wrong_answer"].format(answer.correctTranslation)

        return AnswerResult(
            isCorrect=is_correct,
            correctTranslation=answer.correctTranslation
        )

    except Exception as e:
        logger.error(f"Error submitting answer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES["general_error"]
        )

@router.post("/finish-session", response_model=SessionResult)
async def finish_session(
    session: SessionComplete,
    user_id: Optional[str] = Cookie(None),
    username: Optional[str] = Cookie(None),
    target_language_id: int = DEFAULT_TARGET_LANGUAGE_ID
):
    """Завершает сессию и оценивает прогресс пользователя."""
    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES["unauthorized"]
        )

    try:
        user_id = int(user_id)

        # Получаем связь пользователь-язык
        user_language_id, level = get_or_create_user_language(user_id, target_language_id)

        # Оцениваем сессию и получаем информацию о patch-словах
        increase_patch = evaluator.evaluate_session(user_id, user_language_id, level)

        # Получаем обновленный уровень пользователя
        conn = get_db_connection()
        new_level = level
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT level FROM user_languages WHERE id = %s",
                        (user_language_id,)
                    )
                    result = cur.fetchone()
                    if result and result['level'] != level:
                        new_level = result['level']
        finally:
            if conn:
                close_db_connection(conn)

        return SessionResult(
            status="completed",
            increasePatch=increase_patch,
            newLevel=new_level if new_level != level else None
        )

    except Exception as e:
        logger.error(f"Error finishing session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES["general_error"]
        )
