# Словарь конфигурационных параметров приложения
CONFIG = {
    "SESSION_SIZE": 10,                    # Количество слов в сессии
    "QUARANTINE_MINUTES": 5,               # Временной карантин между повторениями
    "LONG_BREAK_DAYS": 14,                 # Дней в "длинном перерыве"
    "WSR_WEIGHTS": [3, 2, 1],              # Веса сессий для WSR (от новой к старой)
    "LEVEL_UP_THRESHOLD": 85,              # Порог повышения уровня (%)
    "LEVEL_DOWN_THRESHOLD": 55,            # Порог понижения уровня (%)
    "MAX_NEW_WORDS": 5,                    # Максимум новых слов за сессию
    
    # Пороги для категорий слов
    "WEAK_SUCCESS_THRESHOLD": 50,          # Основной порог для слабых слов (%)
    "WEAK_SUCCESS_FALLBACK": 65,           # Запасной порог для слабых слов (%)
    "WEAK_SUCCESS_LAST_RESORT": 80,        # Крайний порог для слабых слов (%)
    "REVIEW_SUCCESS_THRESHOLD": 70,        # Основной порог для повторения (%)
    "REVIEW_SUCCESS_FALLBACK": 60,         # Запасной порог для повторения (%)
    
    # Целевое количество слов по категориям
    "WEAK_WORDS_TARGET": 3,                # Целевое количество слабых слов
    "REVIEW_WORDS_TARGET": 3,              # Целевое количество слов на повторение
    "STRETCH_WORDS_TARGET": 1,             # Целевое количество слов повышенной сложности
    
    # Интервалы давности просмотра
    "LAST_SEEN_DAYS_SHORT": 1,             # Короткий интервал (дни)
    "LAST_SEEN_DAYS_MEDIUM": 7,            # Средний интервал (дни)
    "LAST_SEEN_DAYS_LONG": 30,             # Длинный интервал (дни)
    
    # Пороги для адаптивного выбора новых слов
    "NEW_WORDS_THRESHOLD_LOW": 40,         # Нижний порог (%)
    "NEW_WORDS_THRESHOLD_MID": 60,         # Средний порог (%)
    "NEW_WORDS_THRESHOLD_HIGH": 80,        # Высокий порог (%)
    "NEW_WORDS_COUNT_LOW": 1,              # Мало новых слов
    "NEW_WORDS_COUNT_MID": 2,              # Средне новых слов
    "NEW_WORDS_COUNT_HIGH": 4,             # Много новых слов
    "NEW_WORDS_COUNT_VERY_HIGH": 5         # Очень много новых слов
}

# Соответствие уровня CEFR и сложности (difficulty)
LEVEL_TO_DIFFICULTY = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6
}

# Порядок уровней CEFR для повышения/понижения
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"] 