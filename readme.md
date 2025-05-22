# Flowcado FastAPI

Это обновленная версия приложения Flowcado для изучения иностранных слов, переписанная с использованием FastAPI.

## Особенности

- FastAPI для бэкенд-разработки (вместо Flask)
- API-ориентированная архитектура
- JavaScript для управления сессиями изучения слов на стороне клиента
- Сохранение бизнес-логики оригинального приложения

## Структура проекта

```
new_app/
├── api/                 # API эндпоинты
│   ├── auth.py          # Аутентификация
│   └── words.py         # Работа со словами
├── db/                  # Работа с базой данных
│   └── database.py      # Функции для работы с БД
├── models/              # Модели данных
│   ├── config.py        # Конфигурация
│   ├── messages.py      # Текстовые сообщения
│   └── schemas.py       # Pydantic модели
├── services/            # Сервисы
│   ├── onboarding.py    # Онбординг пользователей
│   ├── picker.py        # Подбор слов
│   └── session_evaluator.py # Оценка сессий
├── static/              # Статические файлы
│   ├── css/
│   │   └── styles.css   # Стили
│   ├── js/
│   │   └── app.js       # JavaScript функции
│   └── index.html       # Главная страница
├── templates/           # Шаблоны (если нужны)
├── main.py              # Основной файл приложения
└── requirements.txt     # Зависимости
```

## Установка и запуск

1. Создайте и активируйте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Настройте переменные окружения:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/flowcado"
# или на Windows
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/flowcado
```

4. Запустите приложение:

```bash
uvicorn main:app --reload
```

5. Откройте браузер и перейдите по адресу: http://localhost:8000

## API эндпоинты

- `GET /api/auth/user` - Получение информации о текущем пользователе
- `POST /api/auth/login` - Вход в систему
- `POST /api/auth/logout` - Выход из системы
- `GET /api/words/start-session` - Начало новой сессии
- `POST /api/words/submit-answer` - Отправка ответа
- `POST /api/words/finish-session` - Завершение сессии

## Отличия от оригинального приложения

1. Используется FastAPI вместо Flask
2. Асинхронная обработка запросов
3. Single-page application (SPA) подход для фронтенда
4. Полная API-ориентированная архитектура
5. Клиент-серверное взаимодействие через JSON API
6. Структурированное управление сессиями через JavaScript класс

## Авторы

- Создано на основе оригинального приложения Flowcado 