/**
 * learn-session.js
 * Клиентский JavaScript для оптимизации сессии изучения слов
 * Обеспечивает быструю отзывчивость интерфейса и асинхронную отправку ответов
 */

class LearningSession {
    constructor() {
        this.words = [];           // Массив из 10 слов
        this.currentIndex = 0;     // Текущий индекс слова
        this.sessionId = null;     // ID сессии
        this.answers = [];         // История ответов
        this.isSubmitting = false; // Флаг отправки ответа
    }

    /**
     * Инициализация сессии обучения
     */
    async init() {
        try {
            // Показываем индикатор загрузки
            this.showLoading(true);
            
            // Запрашиваем 10 слов с сервера
            const response = await fetch('/api/start-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) {
                throw new Error('Не удалось получить слова для сессии');
            }
            
            const data = await response.json();
            
            // Сохраняем данные
            this.words = data.words;
            this.sessionId = data.sessionId;
            this.currentIndex = 0;
            this.answers = [];
            
            // Отображаем первое слово
            this.displayCurrentWord();
            
            // Убираем индикатор загрузки
            this.showLoading(false);
            
            // Настраиваем обработчики событий
            this.setupEventListeners();
            
            return true;
        } catch (error) {
            console.error('Ошибка инициализации сессии:', error);
            this.showError('Не удалось начать сессию. Попробуйте обновить страницу.');
            this.showLoading(false);
            return false;
        }
    }

    /**
     * Настройка обработчиков событий
     */
    setupEventListeners() {
        // Форма ответа
        const form = document.getElementById('answer-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitAnswer();
            });
        }
        
        // Кнопка следующего слова
        const nextButton = document.getElementById('next-button');
        if (nextButton) {
            nextButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.nextWord();
            });
        }
    }

    /**
     * Отображает текущее слово
     */
    displayCurrentWord() {
        if (this.currentIndex >= this.words.length) {
            this.finishSession();
            return;
        }
        
        const word = this.words[this.currentIndex];
        
        // Обновляем отображение слова
        document.getElementById('word-text').textContent = word.text;
        
        // Обновляем варианты ответов
        const optionsContainer = document.getElementById('options-container');
        optionsContainer.innerHTML = '';
        
        word.options.forEach(option => {
            const label = document.createElement('label');
            
            const input = document.createElement('input');
            input.type = 'radio';
            input.name = 'answer';
            input.value = option;
            input.required = true;
            
            const span = document.createElement('span');
            span.textContent = option;
            
            label.appendChild(input);
            label.appendChild(span);
            optionsContainer.appendChild(label);
        });
        
        // Обновляем скрытое поле с ID слова
        document.getElementById('word-id').value = word.id;
        document.getElementById('correct-translation').value = word.correct_translation;
        
        // Обновляем прогресс
        const progressElement = document.getElementById('progress');
        progressElement.textContent = `Слово ${this.currentIndex + 1} из ${this.words.length}`;
        
        // Сбрасываем результат
        this.hideResult();
        
        // Активируем кнопку ответа
        document.getElementById('answer-button').disabled = false;
    }

    /**
     * Отправляет ответ пользователя
     */
    async submitAnswer() {
        try {
            // Предотвращаем дублирование отправки
            if (this.isSubmitting) return;
            this.isSubmitting = true;
            
            // Показываем индикатор загрузки
            this.showSmallLoading(true);
            
            // Получаем данные формы
            const wordId = document.getElementById('word-id').value;
            const correctTranslation = document.getElementById('correct-translation').value;
            
            // Находим выбранный ответ
            const selectedOption = document.querySelector('input[name="answer"]:checked');
            if (!selectedOption) {
                this.showError('Выберите вариант ответа');
                this.isSubmitting = false;
                this.showSmallLoading(false);
                return;
            }
            
            const userAnswer = selectedOption.value;
            
            // Отправляем на сервер
            const response = await fetch('/api/submit-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wordId: parseInt(wordId),
                    userAnswer: userAnswer,
                    sessionId: this.sessionId,
                    correctTranslation: correctTranslation
                })
            });
            
            if (!response.ok) {
                throw new Error('Не удалось отправить ответ');
            }
            
            const result = await response.json();
            
            // Сохраняем ответ локально
            this.answers.push({
                wordId: parseInt(wordId),
                isCorrect: result.isCorrect
            });
            
            // Показываем результат
            this.showResult(result.isCorrect, result.correctTranslation, userAnswer);
            
            // Разблокируем интерфейс
            this.isSubmitting = false;
            this.showSmallLoading(false);
            
        } catch (error) {
            console.error('Ошибка отправки ответа:', error);
            this.showError('Не удалось отправить ответ. Проверьте соединение.');
            this.isSubmitting = false;
            this.showSmallLoading(false);
        }
    }

    /**
     * Показывает результат ответа
     */
    showResult(isCorrect, correctTranslation, userAnswer) {
        // Деактивируем выбор ответов
        const options = document.querySelectorAll('input[name="answer"]');
        options.forEach(option => {
            option.disabled = true;
            
            // Добавляем подсветку для правильного и выбранного ответов
            const label = option.parentElement;
            if (option.value === correctTranslation) {
                label.classList.add('correct');
            } else if (option.value === userAnswer && !isCorrect) {
                label.classList.add('wrong');
            }
        });
        
        // Показываем результат
        const resultContainer = document.getElementById('result-container');
        resultContainer.classList.add(isCorrect ? 'correct' : 'wrong');
        resultContainer.style.display = 'block';
        
        // Используем правильные фразы из messages.py
        let resultMessage;
        if (isCorrect) {
            resultMessage = 'Ура, молодец!'; // SUCCESS_MESSAGES.correct_answer
        } else {
            resultMessage = `Эх, промазал, правильно — «${correctTranslation}»`; // RESULT_MESSAGES.wrong_answer
        }
        
        resultContainer.textContent = resultMessage;
        
        // Деактивируем кнопку ответа
        document.getElementById('answer-button').disabled = true;
        
        // Добавляем кнопку "Следующее слово"
        const nextButtonForm = document.createElement('form');
        nextButtonForm.method = 'get';
        nextButtonForm.action = '/learn';
        nextButtonForm.style.marginTop = '20px';
        
        const nextButton = document.createElement('button');
        nextButton.id = 'next-button';
        nextButton.type = 'submit';
        nextButton.textContent = 'Следующее слово'; // UI_ELEMENTS.next_button
        nextButton.addEventListener('click', (e) => {
            e.preventDefault();
            this.nextWord();
        });
        
        nextButtonForm.appendChild(nextButton);
        resultContainer.appendChild(nextButtonForm);
    }

    /**
     * Скрывает результат ответа
     */
    hideResult() {
        const resultContainer = document.getElementById('result-container');
        resultContainer.classList.remove('correct', 'wrong');
        resultContainer.style.display = 'none';
        resultContainer.textContent = '';
    }

    /**
     * Переход к следующему слову
     */
    nextWord() {
        this.currentIndex++;
        
        if (this.currentIndex >= this.words.length) {
            this.finishSession();
        } else {
            this.displayCurrentWord();
        }
    }

    /**
     * Завершение текущего набора слов и переход к новому
     */
    async finishSession() {
        try {
            // Показываем индикатор загрузки
            this.showLoading(true);
            
            // Отправляем данные о завершении сессии
            const response = await fetch('/api/finish-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sessionId: this.sessionId
                })
            });
            
            if (!response.ok) {
                throw new Error('Не удалось завершить текущую подборку слов');
            }
            
            // Сразу инициализируем новую сессию без показа экрана завершения
            await this.init();
            
        } catch (error) {
            console.error('Ошибка при переходе к новым словам:', error);
            this.showError('Не удалось загрузить новые слова. Проверьте соединение.');
            this.showLoading(false);
        }
    }

    /**
     * Начинает новую сессию
     * Оставляем метод на случай, если мы захотим позже добавить кнопку "Заново" 
     */
    async startNewSession() {
        await this.init();
    }

    /**
     * Показывает/скрывает индикатор загрузки
     */
    showLoading(show) {
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
            
            // Добавляем спиннер, если его нет
            if (show && !loadingElement.querySelector('.spinner')) {
                const spinner = document.createElement('div');
                spinner.className = 'spinner';
                loadingElement.appendChild(spinner);
            }
        }
    }

    /**
     * Показывает/скрывает малый индикатор загрузки
     */
    showSmallLoading(show) {
        const loadingElement = document.getElementById('small-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'inline-block' : 'none';
            
            // Добавляем спиннер, если его нет
            if (show && !loadingElement.querySelector('.spinner')) {
                const spinner = document.createElement('div');
                spinner.className = 'spinner';
                loadingElement.innerHTML = '';
                loadingElement.appendChild(spinner);
            }
        }
    }

    /**
     * Показывает сообщение об ошибке
     */
    showError(message) {
        const errorElement = document.getElementById('error-message');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
            
            // Скрываем сообщение через 5 секунд
            setTimeout(() => {
                errorElement.style.display = 'none';
            }, 5000);
        } else {
            alert(message);
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    const session = new LearningSession();
    window.learningSession = session; // Глобальная доступность для дебаггинга
    
    // Если мы на странице обучения, инициализируем сессию
    if (document.getElementById('learning-container')) {
        session.init();
    }
}); 