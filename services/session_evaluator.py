import logging
from datetime import datetime, timedelta
from db.database import get_db_connection, close_db_connection
from models.config import CONFIG, LEVEL_ORDER

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionEvaluator:
    """Оценивает сессию и рассчитывает WSR для повышения/понижения уровня."""
    
    def __init__(self):
        self.level_up_threshold = CONFIG["LEVEL_UP_THRESHOLD"]
        self.level_down_threshold = CONFIG["LEVEL_DOWN_THRESHOLD"]
        self.wsr_weights = CONFIG["WSR_WEIGHTS"]
        self.long_break_days = CONFIG["LONG_BREAK_DAYS"]
    
    def evaluate_session(self, user_id: int, user_language_id: int, current_level: str) -> bool:
        """
        Оценивает сессию, рассчитывает средневзвешенную успеваемость (WSR) 
        и при необходимости изменяет уровень пользователя.
        Возвращает True если необходимо увеличить количество patch-слов.
        """
        try:
            logger.info(f"Evaluating session for user {user_id}, user_language_id {user_language_id}, level {current_level}")
            
            increase_patch = False
            
            # Получаем последние сессии пользователя
            conn = get_db_connection()
            
            # Проверяем наличие длинного перерыва
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT NOW() - MAX(last_seen) as inactive_period
                        FROM user_progress
                        WHERE user_language_id = %s
                        """, (user_language_id,))
                    result = cur.fetchone()
                    
                    if result and result['inactive_period']:
                        inactive_days = result['inactive_period'].days
                        if inactive_days >= self.long_break_days:
                            logger.info(f"User inactive for {inactive_days} days, suggesting increased patch words")
                            increase_patch = True
            
            # Рассчитываем WSR
            wsr = self._calculate_wsr(user_language_id, conn)
            logger.info(f"Calculated WSR: {wsr:.2f}%")
            
            # Обновляем счетчики достижения порогов повышения/понижения
            level_change = self._update_threshold_counters(user_language_id, wsr, conn)
            
            # Если нужно изменить уровень
            if level_change != 0:
                new_level = self._change_level(current_level, level_change)
                
                if new_level != current_level:
                    self._update_user_level(user_language_id, new_level, conn)
                    logger.info(f"Level changed from {current_level} to {new_level}")
            
            # Проверим наличие колонки increase_patch перед обновлением
            with conn:
                with conn.cursor() as cur:
                    # Проверяем существование колонки increase_patch
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns
                            WHERE table_name = 'user_languages' AND column_name = 'increase_patch'
                        )
                    """)
                    column_exists = cur.fetchone()['exists']
                    
                    if column_exists:
                        # Колонка существует, обновляем её
                        cur.execute("""
                            UPDATE user_languages 
                            SET increase_patch = %s 
                            WHERE id = %s
                        """, (increase_patch, user_language_id))
            
            return increase_patch
            
        except Exception as e:
            logger.error(f"Error evaluating session: {e}")
            return False
        finally:
            if conn:
                close_db_connection(conn)
    
    def _calculate_wsr(self, user_language_id: int, conn) -> float:
        """
        Рассчитывает средневзвешенную успеваемость (WSR) на основе 
        последних сессий пользователя.
        """
        try:
            with conn.cursor() as cur:
                # Получаем результаты последних сессий в точности как в оригинале
                cur.execute("""
                    SELECT 
                        session_id, 
                        SUM(successes) as successes, 
                        SUM(repeats) as repeats
                    FROM user_progress
                    WHERE user_language_id = %s
                    GROUP BY session_id
                    ORDER BY MAX(last_seen) DESC 
                    LIMIT 3
                """, (user_language_id,))
                sessions = cur.fetchall()
                
                if not sessions:
                    return 50.0  # Значение по умолчанию
                
                # Рассчитываем WSR с учетом весов
                total_weight = 0
                weighted_sum = 0
                
                for i, session in enumerate(sessions):
                    if i < len(self.wsr_weights):
                        weight = self.wsr_weights[i]
                    else:
                        weight = 1
                    
                    repeats = session['repeats']
                    successes = session['successes']
                    
                    if repeats > 0:
                        success_rate = (successes / repeats) * 100
                        weighted_sum += success_rate * weight
                        total_weight += weight
                
                if total_weight == 0:
                    return 50.0  # Значение по умолчанию
                
                return weighted_sum / total_weight
                
        except Exception as e:
            logger.error(f"Error calculating WSR: {e}")
            return 50.0  # Значение по умолчанию
    
    def _update_threshold_counters(self, user_language_id: int, wsr: float, conn) -> int:
        """
        Обновляет счетчики достижения порогов повышения/понижения уровня.
        Возвращает: 1 для повышения, -1 для понижения, 0 без изменений.
        """
        try:
            with conn.cursor() as cur:
                # Проверяем существование колонок
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_name = 'user_languages' AND column_name = 'level_up_streak'
                    ) as has_level_up_streak,
                    EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_name = 'user_languages' AND column_name = 'level_down_streak'
                    ) as has_level_down_streak
                """)
                result = cur.fetchone()
                
                if not result or not result['has_level_up_streak'] or not result['has_level_down_streak']:
                    # Колонки не существуют - добавляем их
                    cur.execute("""
                        ALTER TABLE user_languages 
                        ADD COLUMN IF NOT EXISTS level_up_streak INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS level_down_streak INTEGER DEFAULT 0
                    """)
                
                # Получаем текущие счетчики
                cur.execute("""
                    SELECT level_up_streak, level_down_streak
                    FROM user_languages
                    WHERE id = %s
                """, (user_language_id,))
                result = cur.fetchone()
                
                if not result:
                    return 0
                
                level_up_streak = result['level_up_streak'] if result['level_up_streak'] is not None else 0
                level_down_streak = result['level_down_streak'] if result['level_down_streak'] is not None else 0
                
                # Обновляем счетчики на основе WSR
                if wsr >= self.level_up_threshold:
                    level_up_streak += 1
                    level_down_streak = 0
                elif wsr < self.level_down_threshold:
                    level_down_streak += 1
                    level_up_streak = 0
                else:
                    level_up_streak = 0
                    level_down_streak = 0
                
                # Обновляем счетчики в БД
                cur.execute("""
                    UPDATE user_languages
                    SET level_up_streak = %s, level_down_streak = %s
                    WHERE id = %s
                """, (level_up_streak, level_down_streak, user_language_id))
                
                # Проверяем достижение порогов
                if level_up_streak >= 3:
                    # Сбрасываем счетчик
                    cur.execute("""
                        UPDATE user_languages
                        SET level_up_streak = 0
                        WHERE id = %s
                    """, (user_language_id,))
                    return 1
                
                if level_down_streak >= 3:
                    # Сбрасываем счетчик
                    cur.execute("""
                        UPDATE user_languages
                        SET level_down_streak = 0
                        WHERE id = %s
                    """, (user_language_id,))
                    return -1
                
                return 0
                
        except Exception as e:
            logger.error(f"Error updating threshold counters: {e}")
            return 0
    
    def _change_level(self, current_level: str, change: int) -> str:
        """Возвращает новый уровень после повышения/понижения."""
        try:
            current_index = LEVEL_ORDER.index(current_level)
            new_index = current_index + change
            
            # Ограничиваем индекс допустимыми значениями
            if new_index < 0:
                new_index = 0
            elif new_index >= len(LEVEL_ORDER):
                new_index = len(LEVEL_ORDER) - 1
            
            return LEVEL_ORDER[new_index]
            
        except (ValueError, IndexError) as e:
            logger.error(f"Error changing level: {e}")
            return current_level
    
    def _update_user_level(self, user_language_id: int, new_level: str, conn) -> None:
        """Обновляет уровень пользователя в БД."""
        try:
            with conn.cursor() as cur:
                # Проверяем существование колонки level_changed_at
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_name = 'user_languages' AND column_name = 'level_changed_at'
                    )
                """)
                column_exists = cur.fetchone()['exists']
                
                if column_exists:
                    cur.execute("""
                        UPDATE user_languages
                        SET level = %s, level_changed_at = NOW()
                        WHERE id = %s
                    """, (new_level, user_language_id))
                else:
                    cur.execute("""
                        UPDATE user_languages
                        SET level = %s
                        WHERE id = %s
                    """, (new_level, user_language_id))
                
        except Exception as e:
            logger.error(f"Error updating user level: {e}") 