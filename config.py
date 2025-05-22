# config.py
# Хранит конфигурируемые параметры для приложения, согласно спецификации MVP v1.
# Параметры соответствуют таблице "Основные параметры и конфигурация" (раздел 1).

# Основные параметры приложения
CONFIG = {
    # Стартовый уровень для новых пользователей
    "STARTING_LEVEL": "A2",  # Начальная сложность слов (difficulty=2)

    # Размер сессии
    "SESSION_SIZE": 10,  # Количество слов в одной сессии

    # Временной карантин
    "QUARANTINE_MINUTES": 5,  # Запрет повторять слово (кроме Weak) в течение 5 минут

    # Длинный перерыв
    "LONG_BREAK_DAYS": 14,  # Перерыв > 14 дней: заморозка уровня на 2 сессии

    # Вес сессий для Weighted Success Rate (WSR)
    "WSR_WEIGHTS": [3, 2, 1],  # Вес последних трёх сессий (S₀×3 + S₁×2 + S₂×1)

    # Пороги для пересчёта уровня
    "LEVEL_UP_THRESHOLD": 85,  # WSR ≥ 85% для повышения уровня
    "LEVEL_DOWN_THRESHOLD": 55,  # WSR < 55% для понижения уровня (min A1)

    # Максимальное количество новых слов в сессии
    "MAX_NEW_WORDS": 5,  # Увеличенный лимит New-L в Main-bucket + Adaptive

    # Пауза для новых слов после первого показа
    "NEW_WORD_PAUSE_MINUTES": 30,  # Новое слово не становится Weak в течение 30 минут

    # Порог для Adaptive-слота
    "ADAPTIVE_SUCCESS_THRESHOLD": 75,  # recent_success_rate ≥ 75% → Stretch+1, иначе Weak/Patch/New-L
    
    # Параметры для более гибкой выборки слов
    "WEAK_SUCCESS_THRESHOLD": 50,  # Снижен порог для weak слов
    "WEAK_SUCCESS_FALLBACK": 65,  # Запасной порог для weak слов
    "WEAK_SUCCESS_LAST_RESORT": 80,  # Крайний запасной порог для weak слов
    "REVIEW_SUCCESS_THRESHOLD": 70,  # Снижен порог для review слов
    "REVIEW_SUCCESS_FALLBACK": 50,  # Запасной порог для review слов
    
    # Градации для добавления новых слов
    "NEW_WORDS_THRESHOLD_LOW": 40,  # Снижен порог для ограничения новых слов
    "NEW_WORDS_THRESHOLD_MID": 60,  # Ниже этого порога - добавляется 2 новых слова
    "NEW_WORDS_THRESHOLD_HIGH": 80,  # Выше этого порога - добавляется максимум новых слов
    "NEW_WORDS_COUNT_LOW": 1,      # Минимум 1 новое слово даже при низком success rate
    "NEW_WORDS_COUNT_MID": 2,      # Увеличено количество новых слов при среднем success rate
    "NEW_WORDS_COUNT_HIGH": 4,     # Увеличено количество новых слов при высоком success rate
    "NEW_WORDS_COUNT_VERY_HIGH": 5, # При очень высоком success rate (>90%)
    
    # Параметры для гарантированного заполнения сессии
    "LAST_SEEN_DAYS_SHORT": 1,    # Короткий период для повторения
    "LAST_SEEN_DAYS_MEDIUM": 7,   # Средний период для повторения
    "LAST_SEEN_DAYS_LONG": 30,    # Длинный период для повторения
}

# Словарь для преобразования уровня в difficulty
LEVEL_TO_DIFFICULTY = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6
}

# Список уровней для проверки границ (A1 min, C2 max)
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
