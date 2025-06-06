// Класс для управления сессией изучения слов
class LearningSession {
    constructor() {
        this.sessionId = null;
        this.words = [];
        this.currentWordIndex = 0;
        this.totalWords = 0;
        this.selectedOption = null;
    }

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

    moveToNextWord() {
        this.currentWordIndex++;
        this.selectedOption = null;

        if (this.currentWordIndex >= this.words.length) {
            return false;
        }

        return true;
    }

    getCurrentWord() {
        if (this.currentWordIndex < this.words.length) {
            return this.words[this.currentWordIndex];
        }
        return null;
    }

    async loadNextBatch() {
        try {
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

            return await this.start();
        } catch (error) {
            console.error('Ошибка при загрузке новой партии слов:', error);
            return false;
        }
    }
}

async function checkAuth() {
    try {
        const response = await fetch('/api/auth/user');
        const data = await response.json();

        if (data.isLoggedIn) {
            document.getElementById('login-container').style.display = 'none';
            document.getElementById('app-container').style.display = 'block';
            document.getElementById('user-display').textContent = `Привет, ${data.username}!`;

            document.getElementById('session-start').style.display = 'none';
            document.getElementById('learning-session').style.display = 'block';
            document.getElementById('session-complete').style.display = 'none';

            startLearning();

            return true;
        } else {
            document.getElementById('login-container').style.display = 'block';
            document.getElementById('app-container').style.display = 'none';

            return false;
        }
    } catch (error) {
        console.error('Ошибка при проверке авторизации:', error);
        return false;
    }
}

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

        checkAuth();

    } catch (error) {
        console.error('Ошибка при входе:', error);
        alert(error.message || 'Не удалось войти. Попробуйте позже.');
    }
}

async function handleLogout() {
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка выхода');
        }

        document.getElementById('login-container').style.display = 'block';
        document.getElementById('app-container').style.display = 'none';

    } catch (error) {
        console.error('Ошибка при выходе:', error);
        alert(error.message || 'Не удалось выйти. Попробуйте позже.');
    }
}

const learningSession = new LearningSession();

function displayCurrentWord() {
    const word = learningSession.getCurrentWord();

    if (!word) {
        return false;
    }

    document.getElementById('word-counter').textContent =
        `Слово ${learningSession.currentWordIndex + 1} из ${learningSession.totalWords}`;

    document.getElementById('current-word').textContent = word.text;

    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = '';

    word.options.forEach(option => {
        const optionBtn = document.createElement('button');
        optionBtn.className = 'option-btn';
        optionBtn.textContent = option;
        optionBtn.addEventListener('click', () => {
            document.querySelectorAll('.option-btn').forEach(btn => {
                btn.classList.remove('selected');
            });

            optionBtn.classList.add('selected');

            learningSession.selectedOption = option;
        });

        optionsContainer.appendChild(optionBtn);
    });

    document.getElementById('result-container').style.display = 'none';

    return true;
}

async function handleAnswerSubmit() {
    if (!learningSession.selectedOption) {
        alert('Пожалуйста, выберите перевод');
        return;
    }

    const result = await learningSession.submitAnswer(learningSession.selectedOption);

    if (!result) {
        return;
    }

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

    document.querySelectorAll('.option-btn').forEach(btn => {
        if (btn.textContent === result.correctTranslation) {
            btn.classList.add('correct');
        } else if (btn.textContent === learningSession.selectedOption && !result.isCorrect) {
            btn.classList.add('incorrect');
        }
    });

    document.querySelectorAll('.option-btn').forEach(btn => {
        btn.disabled = true;
    });
}

async function handleNextWord() {
    const hasNextWord = learningSession.moveToNextWord();

    if (hasNextWord) {
        displayCurrentWord();
    } else {
        await loadNextWordsAndDisplay();
    }
}

async function loadNextWordsAndDisplay() {
    const success = await learningSession.loadNextBatch();

    if (success) {
        displayCurrentWord();
    } else {
        alert('Не удалось загрузить новые слова. Попробуйте обновить страницу.');
    }
}

async function startLearning() {
    const success = await learningSession.start();

    if (success) {
        displayCurrentWord();
    } else {
        alert('Не удалось начать изучение. Попробуйте обновить страницу.');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();

    document.getElementById('login-btn').addEventListener('click', handleLogin);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);

    if (document.getElementById('start-session-btn')) {
        document.getElementById('start-session-btn').addEventListener('click', startLearning);
    }

    document.getElementById('options-container').addEventListener('click', event => {
        if (event.target.classList.contains('option-btn')) {
            handleAnswerSubmit();
        }
    });

    document.getElementById('next-word-btn').addEventListener('click', handleNextWord);

    // Логика бургер-меню
    const burgerBtn = document.getElementById('burger-btn');
    const burgerDropdown = document.getElementById('burger-dropdown');

    burgerBtn.addEventListener('click', () => {
        burgerDropdown.classList.toggle('active');
    });

    // Закрытие бургер-меню при клике вне его
    document.addEventListener('click', (event) => {
        if (!burgerBtn.contains(event.target) && !burgerDropdown.contains(event.target)) {
            burgerDropdown.classList.remove('active');
        }
    });
});
