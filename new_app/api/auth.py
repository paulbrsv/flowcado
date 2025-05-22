from fastapi import APIRouter, HTTPException, Depends, status, Request, Response, Cookie, Form
from fastapi.responses import RedirectResponse
from typing import Optional
from datetime import datetime, timedelta
import logging
import base64

from db.database import get_db_connection, get_or_create_user, update_user_last_active
from models.schemas import UserCreate, User
from models.messages import ERROR_MESSAGES, SUCCESS_MESSAGES

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/login")
async def login(username: str = Form(...), response: Response = None):
    """Вход пользователя в систему по имени."""
    logger.debug(f"Начало входа пользователя: {username}")
    if not username or username.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES["no_username"]
        )
    
    # Получаем или создаем пользователя
    try:
        clean_username = username.strip()
        logger.debug(f"Получаем или создаем пользователя: {clean_username}")
        user_id = get_or_create_user(clean_username)
        logger.debug(f"Пользователь получен, ID: {user_id}")
        
        # Обновляем время последней активности
        logger.debug(f"Обновляем время последней активности для пользователя ID: {user_id}")
        update_user_last_active(user_id)
        
        # Кодируем имя пользователя в base64 для избежания проблем с кодировкой
        encoded_username = base64.b64encode(clean_username.encode('utf-8')).decode('ascii')
        logger.debug(f"Закодированное имя пользователя: {encoded_username}")
        
        # Устанавливаем cookie
        logger.debug("Устанавливаем cookies для пользователя")
        response.set_cookie(
            key="username",
            value=encoded_username,
            max_age=30*24*60*60,  # 30 дней
            httponly=True
        )
        response.set_cookie(
            key="user_id",
            value=str(user_id),
            max_age=30*24*60*60,  # 30 дней
            httponly=True
        )
        
        logger.debug("Вход успешен, возвращаем данные пользователя")
        return {"status": "success", "userId": user_id, "username": clean_username}
        
    except Exception as e:
        logger.error(f"Ошибка при входе пользователя: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES["general_error"]
        )

@router.post("/logout")
async def logout(response: Response):
    """Выход пользователя из системы."""
    # Удаляем cookies
    response.delete_cookie("username")
    response.delete_cookie("user_id")
    
    return {"status": "success", "message": SUCCESS_MESSAGES["logout_success"]}

@router.get("/user")
async def get_current_user(
    user_id: Optional[str] = Cookie(None),
    username: Optional[str] = Cookie(None)
):
    """Возвращает информацию о текущем пользователе."""
    if not user_id or not username:
        return {"isLoggedIn": False}
    
    try:
        # Декодируем имя пользователя из base64
        try:
            decoded_username = base64.b64decode(username).decode('utf-8')
        except:
            # Если не удалось декодировать, используем как есть (для обратной совместимости)
            decoded_username = username
        
        # Обновляем время последней активности
        update_user_last_active(int(user_id))
        
        return {
            "isLoggedIn": True,
            "userId": int(user_id),
            "username": decoded_username
        }
    except Exception:
        return {"isLoggedIn": False} 