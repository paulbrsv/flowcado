from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import logging
import uuid
from db_access import (
    get_or_create_user, get_or_create_user_language, update_user_last_active
)
from onboarding import select_onboarding_words
from picker import select_words
from answer_handler import handle_answer
from session_evaluator import SessionEvaluator
from config import CONFIG
from messages import ERROR_MESSAGES, SUCCESS_MESSAGES, RESULT_MESSAGES, UI_ELEMENTS

# Настройка приложения и логирования
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Заменить на безопасный ключ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация оценщика сессий
evaluator = SessionEvaluator()

@app.route("/", methods=["GET", "POST"])
def index():
    """Стартовая страница: начало сессии или ввод имени."""
    try:
        if request.method == "POST":
            username = request.form.get("username")
            if not username:
                flash(ERROR_MESSAGES["no_username"])
                return render_template("index.html", 
                                      success_messages=SUCCESS_MESSAGES,
                                      ui_elements=UI_ELEMENTS)

            # Получаем или создаём пользователя
            user_id = get_or_create_user(username)
            target_language_id = 1  # Английский
            user_language_id, level = get_or_create_user_language(user_id, target_language_id)
            update_user_last_active(user_id)

            # Сохраняем данные в сессии
            session["user_id"] = user_id
            session["user_language_id"] = user_language_id
            session["level"] = level
            session["current_word_index"] = 0
            session["answers"] = []
            session["session_id"] = str(uuid.uuid4())

            # Выбираем слова
            words = select_onboarding_words(user_id, target_language_id, user_language_id)
            if not words:
                # Не новичок, используем picker
                increase_patch = evaluator.evaluate_session(user_id, user_language_id, level)
                session["increase_patch"] = increase_patch
                words = select_words(user_id, target_language_id, user_language_id, level)

            if not words or len(words) < CONFIG["SESSION_SIZE"]:
                flash(ERROR_MESSAGES["insufficient_words"])
                return render_template("index.html", 
                                      success_messages=SUCCESS_MESSAGES,
                                      ui_elements=UI_ELEMENTS)

            session["words"] = words
            return redirect(url_for("learn"))

        return render_template("index.html", 
                              success_messages=SUCCESS_MESSAGES,
                              ui_elements=UI_ELEMENTS)

    except Exception as e:
        logger.error(f"Error in index: {e}")
        flash(ERROR_MESSAGES["general_error"])
        return render_template("index.html", 
                              success_messages=SUCCESS_MESSAGES,
                              ui_elements=UI_ELEMENTS)

@app.route("/learn", methods=["GET", "POST"])
def learn():
    """Отображает текущее слово, обрабатывает ответы и переходит к следующему."""
    try:
        if "words" not in session or "user_language_id" not in session:
            return redirect(url_for("index"))

        word_index = session["current_word_index"]
        words = session["words"]

        if word_index >= len(words):
            # Сессия завершена
            increase_patch = evaluator.evaluate_session(
                session["user_id"], session["user_language_id"], session["level"]
            )
            session["increase_patch"] = increase_patch
            
            # Удаляем только данные этой сессии слов, оставляя пользователя залогиненным
            session.pop("words", None)
            session.pop("current_word_index", None)
            
            # Устанавливаем флаг завершения сессии
            session["session_completed"] = True
            
            # Вместо перенаправления на index, подбираем новые слова для того же пользователя
            user_id = session["user_id"]
            user_language_id = session["user_language_id"]
            level = session["level"]
            target_language_id = 1  # Английский, можно сохранять в сессии если будет больше языков
            
            # Сброс индекса текущего слова для новой сессии
            session["current_word_index"] = 0
            session["answers"] = []
            session["session_id"] = str(uuid.uuid4())
            
            # Выбираем новые слова
            words = select_words(user_id, target_language_id, user_language_id, level)
            
            if not words or len(words) < CONFIG["SESSION_SIZE"]:
                flash(ERROR_MESSAGES["insufficient_words"])
                # Если не удалось подобрать слова, показываем сообщение
                # и перенаправляем на специальную страницу отдыха
                return render_template("rest.html", 
                                     success_messages=SUCCESS_MESSAGES,
                                     ui_elements=UI_ELEMENTS)
            
            # Сохраняем новые слова в сессии
            session["words"] = words
            
            # Перенаправляем на страницу обучения с новыми словами
            return redirect(url_for("learn"))

        current_word = words[word_index]
        result = None
        selected_answer = None

        if request.method == "POST":
            word_id = int(request.form.get("word_id"))
            user_answer = request.form.get("answer")

            if not user_answer:
                flash(ERROR_MESSAGES["no_answer"])
                return redirect(url_for("learn"))

            if current_word["id"] != word_id:
                flash(ERROR_MESSAGES["word_mismatch"])
                return redirect(url_for("learn"))

            is_correct = user_answer == current_word["correct_translation"]
            handle_answer(
                session["user_language_id"],
                word_id,
                is_correct,
                session["session_id"]
            )

            session["answers"].append({
                "word_id": word_id,
                "is_correct": is_correct
            })

            result = {
                "correct": is_correct,
                "correct_translation": current_word["correct_translation"]
            }
            session["result"] = result  # Сохраняем результат в сессии для последующей проверки
            selected_answer = user_answer
            
            # Когда пользователь нажимает "Следующее слово" в шаблоне, отправляется GET запрос
            # Мы НЕ увеличиваем индекс здесь, чтобы пользователь мог видеть результат

        # При GET запросе после ответа, увеличиваем счетчик и переходим к следующему слову
        if request.method == "GET" and "result" in session:
            session.pop("result", None)  # Удаляем результат предыдущего ответа
            session["current_word_index"] += 1  # Увеличиваем индекс для следующего слова
            return redirect(url_for("learn"))  # Перенаправляем обратно для отображения нового слова

        # При GET или после ответа показываем слово
        return render_template(
            "learn.html",
            word=current_word,
            options=current_word["options"],
            current_word=word_index + 1,
            total_words=CONFIG["SESSION_SIZE"],
            result=result,
            selected_answer=selected_answer,
            success_messages=SUCCESS_MESSAGES,
            result_messages=RESULT_MESSAGES,
            ui_elements=UI_ELEMENTS
        )

    except Exception as e:
        logger.error(f"Error in learn: {e}")
        flash(ERROR_MESSAGES["general_error"])
        return redirect(url_for("index"))

@app.route("/logout")
def logout():
    """Выход из системы."""
    # Очищаем сессию
    session.clear()
    flash(SUCCESS_MESSAGES["logout_success"])
    return redirect(url_for("index"))

# Новые API-эндпоинты для оптимизированного подхода
@app.route("/api/start-session", methods=["POST"])
def api_start_session():
    """API для получения подборки из 10 слов."""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Пользователь не аутентифицирован"}), 401
        
        user_language_id = session.get("user_language_id")
        level = session.get("level")
        target_language_id = 1  # Английский
        
        # Создаем новую ID сессии
        session_id = str(uuid.uuid4())
        
        # Выбираем слова
        words = select_words(user_id, target_language_id, user_language_id, level)
        
        if not words or len(words) < CONFIG["SESSION_SIZE"]:
            return jsonify({"error": "Недостаточно слов для сессии"}), 400
        
        # Возвращаем данные для клиента
        return jsonify({
            "sessionId": session_id,
            "words": words,
            "totalWords": CONFIG["SESSION_SIZE"]
        })
    
    except Exception as e:
        logger.error(f"Error in api_start_session: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

@app.route("/api/submit-answer", methods=["POST"])
def api_submit_answer():
    """API для обработки ответа на слово."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Отсутствуют данные запроса"}), 400
        
        word_id = data.get("wordId")
        user_answer = data.get("userAnswer")
        session_id = data.get("sessionId")
        correct_translation = data.get("correctTranslation")
        
        if not all([word_id, user_answer, session_id, correct_translation]):
            return jsonify({"error": "Недостаточно данных для обработки ответа"}), 400
        
        # Проверяем правильность ответа
        is_correct = user_answer == correct_translation
        
        # Обрабатываем ответ
        handle_answer(
            session.get("user_language_id"),
            word_id,
            is_correct,
            session_id
        )
        
        # Сохраняем ответ в сессии (для статистики)
        if "answers" not in session:
            session["answers"] = []
        
        session["answers"].append({
            "word_id": word_id,
            "is_correct": is_correct
        })
        
        # Возвращаем результат
        return jsonify({
            "isCorrect": is_correct,
            "correctTranslation": correct_translation
        })
    
    except Exception as e:
        logger.error(f"Error in api_submit_answer: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

@app.route("/api/finish-session", methods=["POST"])
def api_finish_session():
    """API для завершения сессии и оценки прогресса."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Отсутствуют данные запроса"}), 400
        
        session_id = data.get("sessionId")
        
        if not session_id:
            return jsonify({"error": "Отсутствует ID сессии"}), 400
        
        # Оцениваем сессию
        increase_patch = evaluator.evaluate_session(
            session.get("user_id"), 
            session.get("user_language_id"), 
            session.get("level")
        )
        
        # Очищаем старые данные сессии
        if "answers" in session:
            session.pop("answers")
        
        # Возвращаем результат и информацию о следующих шагах
        return jsonify({
            "status": "success",
            "increasePatch": increase_patch,
            "newLevel": session.get("level")
        })
    
    except Exception as e:
        logger.error(f"Error in api_finish_session: {e}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

if __name__ == "__main__":
    app.run(debug=True)
