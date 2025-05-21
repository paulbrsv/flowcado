# session_evaluator.py
# Пересчитывает уровень пользователя после сессии, рассчитывает WSR.
# Соответствует спецификации MVP v1, раздел 6.

import logging
from datetime import datetime, timedelta
from db_access import get_session_success_rates, set_user_level, get_user_last_active
from config import CONFIG, LEVEL_ORDER

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionEvaluator:
    def __init__(self):
        # Храним историю WSR для проверки "три сессии подряд"
        self.wsr_history = []
        # Счётчик сессий после перерыва
        self.break_session_count = 0
        # Флаг заморозки уровня
        self.level_frozen = False

    def evaluate_session(self, user_id, user_language_id, current_level):
        """Оценивает сессию, обновляет уровень, возвращает флаг увеличения Patch-1."""
        try:
            logger.info(f"Evaluating session for user {user_id}, user_language_id {user_language_id}, level {current_level}")

            # Проверяем перерыв
            last_active = get_user_last_active(user_id)
            long_break = False
            if last_active and (datetime.now() - last_active) > timedelta(days=CONFIG["LONG_BREAK_DAYS"]):
                logger.info(f"Long break detected (> {CONFIG['LONG_BREAK_DAYS']} days)")
                long_break = True
                self.level_frozen = True
                self.break_session_count = 0

            # Увеличиваем счётчик сессий после перерыва
            if self.level_frozen:
                self.break_session_count += 1
                if self.break_session_count >= 2:
                    self.level_frozen = False
                    self.break_session_count = 0
                    logger.info("Level freeze lifted after 2 sessions")

            # Получаем success_rate для последних трёх сессий
            session_rates = get_session_success_rates(user_language_id, num_sessions=3)
            if not session_rates:
                logger.info("No session data yet, skipping evaluation")
                return False  # increase_patch не требуется

            # Рассчитываем WSR
            weights = CONFIG["WSR_WEIGHTS"]
            weighted_sum = sum(rate * weight for rate, weight in zip(session_rates, weights[:len(session_rates)]))
            total_weight = sum(weights[:len(session_rates)])
            wsr = weighted_sum / total_weight if total_weight > 0 else 0
            logger.info(f"Calculated WSR: {wsr:.2f}%")

            # Сохраняем WSR в историю
            self.wsr_history.append(wsr)
            if len(self.wsr_history) > 3:
                self.wsr_history.pop(0)

            # Проверяем условия изменения уровня
            if not self.level_frozen:
                if len(self.wsr_history) == 3:
                    level_changed = False
                    if all(w >= CONFIG["LEVEL_UP_THRESHOLD"] for w in self.wsr_history):
                        # Повышаем уровень
                        current_idx = LEVEL_ORDER.index(current_level)
                        if current_idx < len(LEVEL_ORDER) - 1:
                            new_level = LEVEL_ORDER[current_idx + 1]
                            set_user_level(user_language_id, new_level)
                            logger.info(f"Level increased: {current_level} -> {new_level}")
                            level_changed = True
                    elif all(w < CONFIG["LEVEL_DOWN_THRESHOLD"] for w in self.wsr_history):
                        # Понижаем уровень
                        current_idx = LEVEL_ORDER.index(current_level)
                        if current_idx > 0:  # Не ниже A1
                            new_level = LEVEL_ORDER[current_idx - 1]
                            set_user_level(user_language_id, new_level)
                            logger.info(f"Level decreased: {current_level} -> {new_level}")
                            level_changed = True
                    
                    if level_changed:
                        self.wsr_history.clear()  # Сбрасываем историю после изменения уровня

            # Возвращаем флаг увеличения Patch-1 (3 слова вместо 1)
            increase_patch = long_break and self.break_session_count <= 2
            if increase_patch:
                logger.info("Patch-1 increased to 3 words due to long break")
            
            return increase_patch

        except Exception as e:
            logger.error(f"Error in evaluate_session: {e}")
            raise