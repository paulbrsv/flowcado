# messages.py
# Модуль для хранения текстовых сообщений приложения

# Сообщения ошибок
ERROR_MESSAGES = {
    "no_username": "Пожалуйста, введите имя",
    "insufficient_words": "Недостаточно слов для сессии. Попробуйте позже.",
    "general_error": "Произошла ошибка. Попробуйте снова.",
    "no_answer": "Выберите перевод",
    "word_mismatch": "Ошибка: слово не совпадает. Попробуйте снова."
}

# Сообщения успеха
SUCCESS_MESSAGES = {
    "correct_answer": "Ура, молодец!",
    "session_completed": "Сессия завершена! Начните новую."
}

# Сообщения о результатах
RESULT_MESSAGES = {
    "wrong_answer": "Эх, промазал, правильно — «{}»"
}

# Элементы интерфейса
UI_ELEMENTS = {
    "answer_button": "Ответить",
    "next_button": "Следующее слово",
    "create_button": "Создать",
    "word_progress": "Слово {} из {}"
} 