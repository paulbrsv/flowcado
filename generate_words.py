import json
import random

def generate_words():
    words = [
        {
            "word": "adventure",
            "level": "A2",
            "frequency": "medium",
            "meanings": [
                {
                    "definition": "an unusual, exciting, or dangerous experience",
                    "translation": "приключение",
                    "examples": [
                        {"en": "We had quite an adventure finding our way back to the hotel.", "ru": "У нас было настоящее приключение, когда мы искали дорогу обратно к отелю."},
                        {"en": "She loves reading books about adventure and exploration.", "ru": "Она любит читать книги о приключениях и исследованиях."}
                    ]
                }
            ]
        },
        {
            "word": "beautiful",
            "level": "A1",
            "frequency": "high",
            "meanings": [
                {
                    "definition": "pleasing the senses or mind aesthetically",
                    "translation": "красивый",
                    "examples": [
                        {"en": "She wore a beautiful dress to the party.", "ru": "Она надела красивое платье на вечеринку."},
                        {"en": "The sunset was beautiful tonight.", "ru": "Сегодняшний закат был просто великолепен."}
                    ]
                }
            ]
        },
        {
            "word": "challenge",
            "level": "B1",
            "frequency": "high",
            "meanings": [
                {
                    "definition": "a task or situation that tests someone's abilities",
                    "translation": "вызов, испытание",
                    "examples": [
                        {"en": "Learning a new language is always a challenge.", "ru": "Изучение нового языка всегда является испытанием."},
                        {"en": "He accepted the challenge to climb the mountain.", "ru": "Он принял вызов — взобраться на гору."}
                    ]
                }
            ]
        },
        {
            "word": "delicate",
            "level": "B2",
            "frequency": "medium",
            "meanings": [
                {
                    "definition": "very fine in texture or structure",
                    "translation": "нежный, хрупкий",
                    "examples": [
                        {"en": "She has delicate features.", "ru": "У неё нежные черты лица."},
                        {"en": "The vase is very delicate, so be careful.", "ru": "Эта ваза очень хрупкая, будь осторожен."}
                    ]
                }
            ]
        },
        {
            "word": "enthusiasm",
            "level": "C1",
            "frequency": "medium",
            "meanings": [
                {
                    "definition": "intense and eager enjoyment, interest, or approval",
                    "translation": "энтузиазм",
                    "examples": [
                        {"en": "Her enthusiasm for the project was contagious.", "ru": "Её энтузиазм по отношению к проекту был заразителен."},
                        {"en": "The team approached the task with great enthusiasm.", "ru": "Команда приступила к задаче с большим энтузиазмом."}
                    ]
                }
            ]
        }
    ]

    # Генерируем оставшиеся слова
    levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    frequencies = ['low', 'medium', 'high']

    additional_words = [
        {"word": "apple", "level": "A1", "frequency": "high", "meanings": [{"definition": "a round fruit with red or green skin", "translation": "яблоко", "examples": [{"en": "I eat an apple every morning.", "ru": "Я ем яблоко каждое утро."}]}]},
        {"word": "brave", "level": "A2", "frequency": "medium", "meanings": [{"definition": "ready to face and endure danger or pain", "translation": "смелый", "examples": [{"en": "The firefighter was very brave.", "ru": "Пожарный был очень смелым."}]}]},
        {"word": "curious", "level": "B1", "frequency": "medium", "meanings": [{"definition": "eager to know or learn something", "translation": "любознательный", "examples": [{"en": "Children are always curious about the world.", "ru": "Дети всегда любознательны к миру."}]}]},
        {"word": "diverse", "level": "B2", "frequency": "medium", "meanings": [{"definition": "showing a great deal of variety", "translation": "разнообразный", "examples": [{"en": "Our city has a diverse population.", "ru": "В нашем городе очень разнообразное население."}]}]},
        {"word": "eloquent", "level": "C1", "frequency": "low", "meanings": [{"definition": "fluent or persuasive in speaking or writing", "translation": "красноречивый", "examples": [{"en": "His eloquent speech moved the audience.", "ru": "Его красноречивая речь тронула аудиторию."}]}]},
        {"word": "fascinating", "level": "C2", "frequency": "low", "meanings": [{"definition": "extremely interesting", "translation": "захватывающий", "examples": [{"en": "The documentary was absolutely fascinating.", "ru": "Документальный фильм был просто захватывающим."}]}]}
    ]

    words.extend(additional_words)

    # Добавляем еще случайные слова
    random_words = [
        {"word": "adventure", "level": "A2", "frequency": "medium", "meanings": [{"definition": "an unusual, exciting experience", "translation": "приключение", "examples": [{"en": "We had an adventure in the mountains.", "ru": "У нас было приключение в горах."}]}]},
        {"word": "brilliant", "level": "B1", "frequency": "medium", "meanings": [{"definition": "very intelligent", "translation": "блестящий", "examples": [{"en": "She is a brilliant student.", "ru": "Она блестящая студентка."}]}]},
        {"word": "compassion", "level": "C1", "frequency": "low", "meanings": [{"definition": "sympathetic concern for others", "translation": "сострадание", "examples": [{"en": "He showed great compassion.", "ru": "Он проявил большое сострадание."}]}]},
        {"word": "diligent", "level": "B2", "frequency": "low", "meanings": [{"definition": "having or showing care and conscientiousness", "translation": "прилежный", "examples": [{"en": "She is a diligent worker.", "ru": "Она прилежная работница."}]}]},
        {"word": "elegant", "level": "C1", "frequency": "medium", "meanings": [{"definition": "graceful and stylish", "translation": "элегантный", "examples": [{"en": "She wore an elegant dress.", "ru": "Она надела элегантное платье."}]}]}
    ]

    words.extend(random_words)

    # Генерируем оставшиеся слова
    for i in range(len(words), 500):
        word = {
            "word": f"word{i}",
            "level": random.choice(levels),
            "frequency": random.choice(frequencies),
            "meanings": [{
                "definition": f"Definition for word{i}",
                "translation": f"Перевод слова{i}",
                "examples": [
                    {
                        "en": f"Example sentence for word{i}.",
                        "ru": f"Пример предложения для слова{i}."
                    }
                ]
            }]
        }
        words.append(word)

    return words

# Генерируем и сохраняем слова
words_list = generate_words()
with open('words.json', 'w', encoding='utf-8') as f:
    json.dump(words_list, f, ensure_ascii=False, indent=2)

print(f"Сгенерировано {len(words_list)} слов в файле words.json") 