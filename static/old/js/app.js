// Класс для управления сессией изучения слов
class LearningSession {
    constructor() {
        this.sessionId = null;
        this.words = [];
        this.currentWordIndex = 0;
        this.totalWords = 0;
        this.selectedOption = null;
    }

    // Инициализация новой сессии
    async start() {
        try {
            const response = await fetch('/api/words/start-session');

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Не удалось начать сессию');
            }

            const data = await response.json();

            this.sessionId = data.sessionId;
            this.words = data.words;
            this.totalWords = data.totalWords;
            this.currentWordIndex = 0;

            return true;
        } catch (error) {
            console.error('Ошибка при запуске сессии:', error);
            alert(error.message || 'Не удалось начать сессию. Попробуйте позже.');
            return false;
        }
    }

    // Проверка ответа пользователя
    async submitAnswer(userAnswer) {
        if (!this.sessionId || this.currentWordIndex >= this.words.length) {
            return null;
        }

        const currentWord = this.words[this.currentWordIndex];

        try {
            const response = await fetch('/api/words/submit-answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    wordId: currentWord.wordId,
                    userAnswer: userAnswer,
                    sessionId: this.sessionId,
                    correctTranslation: currentWord.correctTranslation
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Не удалось отправить ответ');
            }

            return await response.json();
        } catch (error) {
            console.error('Ошибка при отправке ответа:', error);
            alert(error.message || 'Не удалось отправить ответ. Попробуйте позже.');
            return null;
        }
    }

    // Переход к следующему слову
    moveToNextWord() {
        this.currentWordIndex++;
        this.selectedOption = null;

        // Если все слова закончились, загружаем новую партию слов
        if (this.currentWordIndex >= this.words.length) {
            return false;
        }

        return true;
    }

    // Получение текущего слова
    getCurrentWord() {
        if (this.currentWordIndex < this.words.length) {
            return this.words[this.currentWordIndex];
        }
        return null;
    }

    // Завершение текущей партии и загрузка новой
    async loadNextBatch() {
        try {
            // Сначала тихо завершаем текущую сессию
            if (this.sessionId) {
                await fetch('/api/words/finish-session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        sessionId: this.sessionId
                    })
                });
            }

            // Загружаем новую партию слов
            return await this.start();
        } catch (error) {
            console.error('Ошибка при загрузке новой партии слов:', error);
            return false;
        }
    }
}

// Функция для проверки авторизации и обновления UI
async function checkAuth() {
    try {
        const response = await fetch('/api/auth/user');
        const data = await response.json();

        if (data.isLoggedIn) {
            // Пользователь авторизован
            document.getElementById('login-container').style.display = 'none';
            document.getElementById('app-container').style.display = 'block';
            document.getElementById('user-display').textContent = `Привет, ${data.username}!`;

            // Сразу показываем интерфейс сессии и начинаем сессию
            document.getElementById('session-start').style.display = 'none';
            document.getElementById('learning-session').style.display = 'block';
            document.getElementById('session-complete').style.display = 'none';

            // Автоматически запускаем сессию
            startLearning();

            return true;
        } else {
            // Пользователь не авторизован
            document.getElementById('login-container').style.display = 'block';
            document.getElementById('app-container').style.display = 'none';

            return false;
        }
    } catch (error) {
        console.error('Ошибка при проверке авторизации:', error);
        return false;
    }
}

// Обработчик формы входа
async function handleLogin(event) {
    event.preventDefault();

    const username = document.getElementById('username').value.trim();

    if (!username) {
        alert('Пожалуйста, введите имя пользователя');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('username', username);

        const response = await fetch('/api/auth/login', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка входа');
        }

        // Обновляем UI после успешного входа и автоматически начинаем сессию
        checkAuth();

    } catch (error) {
        console.error('Ошибка при входе:', error);
        alert(error.message || 'Не удалось войти. Попробуйте позже.');
    }
}

// Обработчик выхода из системы
async function handleLogout() {
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка выхода');
        }

        // Обновляем UI после выхода
        document.getElementById('login-container').style.display = 'block';
        document.getElementById('app-container').style.display = 'none';

    } catch (error) {
        console.error('Ошибка при выходе:', error);
        alert(error.message || 'Не удалось выйти. Попробуйте позже.');
    }
}

// Создаем экземпляр класса LearningSession
const learningSession = new LearningSession();

// Функция для отображения текущего слова
function displayCurrentWord() {
    const word = learningSession.getCurrentWord();

    if (!word) {
        return false;
    }

    // Обновляем счетчик слов
    document.getElementById('word-counter').textContent =
        `Слово ${learningSession.currentWordIndex + 1} из ${learningSession.totalWords}`;

    // Обновляем текст слова
    document.getElementById('current-word').textContent = word.text;

    // Очищаем варианты ответов
    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = '';

    // Добавляем варианты ответов
    word.options.forEach(option => {
        const optionBtn = document.createElement('button');
        optionBtn.className = 'option-btn';
        optionBtn.textContent = option;
        optionBtn.addEventListener('click', () => {
            // Сбрасываем выделение для всех кнопок
            document.querySelectorAll('.option-btn').forEach(btn => {
                btn.classList.remove('selected');
            });

            // Выделяем выбранную кнопку
            optionBtn.classList.add('selected');

            // Сохраняем выбранный вариант
            learningSession.selectedOption = option;
        });

        optionsContainer.appendChild(optionBtn);
    });

    // Скрываем результат
    document.getElementById('result-container').style.display = 'none';

    return true;
}

// Функция для обработки ответа пользователя
async function handleAnswerSubmit() {
    if (!learningSession.selectedOption) {
        alert('Пожалуйста, выберите перевод');
        return;
    }

    const result = await learningSession.submitAnswer(learningSession.selectedOption);

    if (!result) {
        return;
    }

    // Отображаем результат
    const resultContainer = document.getElementById('result-container');
    const resultMessage = document.getElementById('result-message');

    resultContainer.style.display = 'block';

    if (result.isCorrect) {
        resultMessage.textContent = 'Ура, молодец!';
        resultMessage.className = 'result-message correct';
    } else {
        resultMessage.textContent = `Эх, промазал, правильно — «${result.correctTranslation}»`;
        resultMessage.className = 'result-message incorrect';
    }

    // Подсвечиваем правильный и выбранный варианты
    document.querySelectorAll('.option-btn').forEach(btn => {
        if (btn.textContent === result.correctTranslation) {
            btn.classList.add('correct');
        } else if (btn.textContent === learningSession.selectedOption && !result.isCorrect) {
            btn.classList.add('incorrect');
        }
    });

    // Блокируем кнопки вариантов
    document.querySelectorAll('.option-btn').forEach(btn => {
        btn.disabled = true;
    });
}

// Функция для перехода к следующему слову
async function handleNextWord() {
    const hasNextWord = learningSession.moveToNextWord();

    if (hasNextWord) {
        displayCurrentWord();
    } else {
        // Если слова закончились, загружаем новую партию слов
        await loadNextWordsAndDisplay();
    }
}

// Функция загрузки новой партии слов и отображения
async function loadNextWordsAndDisplay() {
    const success = await learningSession.loadNextBatch();

    if (success) {
        displayCurrentWord();
    } else {
        // В случае ошибки, показываем сообщение
        alert('Не удалось загрузить новые слова. Попробуйте обновить страницу.');
    }
}

// Функция для начала изучения
async function startLearning() {
    // Запускаем сессию
    const success = await learningSession.start();

    if (success) {
        displayCurrentWord();
    } else {
        // В случае ошибки, возможно, стоит показать какое-то сообщение
        alert('Не удалось начать изучение. Попробуйте обновить страницу.');
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем авторизацию при загрузке страницы
    checkAuth();

    // Обработчики событий
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);

    // Если пользователь случайно попадет на экран начала сессии, кнопка должна работать
    if (document.getElementById('start-session-btn')) {
        document.getElementById('start-session-btn').addEventListener('click', startLearning);
    }

    // Создаем делегированный обработчик для вариантов ответов
    document.getElementById('options-container').addEventListener('click', event => {
        if (event.target.classList.contains('option-btn')) {
            handleAnswerSubmit();
        }
    });

    document.getElementById('next-word-btn').addEventListener('click', handleNextWord);
}); 
