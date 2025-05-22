from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import logging
import uuid
from typing import Dict, List, Optional, Any

# Импорт модулей приложения
from db.database import get_db_session
from api.auth import router as auth_router
from api.words import router as words_router
from services.session_evaluator import SessionEvaluator
from models.config import CONFIG

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание приложения FastAPI
app = FastAPI(
    title="Flowcado",
    description="Приложение для изучения иностранных слов",
    version="1.0.0"
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Шаблоны для HTML страниц
templates = Jinja2Templates(directory="templates")

# CORS настройки для API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене нужно указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров API
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(words_router, prefix="/api/words", tags=["words"])

# Инициализация оценщика сессий
evaluator = SessionEvaluator()

# Корневой маршрут - перенаправление на статичный index.html
@app.get("/", response_class=HTMLResponse)
async def redirect_to_index():
    return RedirectResponse(url="/static/index.html")

# Запуск приложения (для отладки)
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 