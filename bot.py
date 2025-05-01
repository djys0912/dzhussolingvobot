import pandas as pd
import json
import os
import logging
from dotenv import load_dotenv
load_dotenv()
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# URL вашего веб-приложения (замените на свой после загрузки на хостинг)
WEBAPP_URL = "https://djys0912.github.io/dzhussolingvobot/german_app.html"

# Функция для загрузки данных из Google Таблицы или локального файла
def load_data():
    file_path = 'words_data.json'  # Путь к файлу для сохранения данных
    
    try:
        # Если файл существует, загружаем данные из локального файла
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            logger.info("Загружены данные из локального файла.")
        else:
            # Если файла нет, пробуем загрузить данные из Google Таблицы
            try:
                url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQH5SmbRNLl9UJ3PU9HRkwmf6AouHGfXqslHqqJbtSP8CZaDpbjl3z2s8Ex9EUBuPMA5HofhJX7K7Fpt/pub?output=csv'
                df = pd.read_csv(url)  # Загружаем данные с таблицы
                data = df.to_dict(orient='records')  # Преобразуем в список словарей
                
                # Сохраняем данные локально для следующего использования
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                logger.info("Данные загружены с Google Таблицы и сохранены локально.")
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных из Google Таблицы: {e}")
                # Создаем тестовые данные, если не удалось загрузить
                data = [
                    {
                        "Слово (DE)": "der Hund",
                        "Правильный ответ": "собака",
                        "Неверный 1": "кошка",
                        "Неверный 2": "мышь",
                        "Неверный 3": "птица"
                    },
                    {
                        "Слово (DE)": "das Haus",
                        "Правильный ответ": "дом",
                        "Неверный 1": "машина",
                        "Неверный 2": "улица",
                        "Неверный 3": "парк"
                    },
                    {
                        "Слово (DE)": "die Frau",
                        "Правильный ответ": "женщина",
                        "Неверный 1": "мужчина",
                        "Неверный 2": "ребенок",
                        "Неверный 3": "девочка"
                    },
                    {
                        "Слово (DE)": "der Mann",
                        "Правильный ответ": "мужчина",
                        "Неверный 1": "женщина",
                        "Неверный 2": "мальчик",
                        "Неверный 3": "девочка"
                    },
                    {
                        "Слово (DE)": "das Kind",
                        "Правильный ответ": "ребенок",
                        "Неверный 1": "взрослый",
                        "Неверный 2": "родитель",
                        "Неверный 3": "учитель"
                    },
                    {
                        "Слово (DE)": "die Katze",
                        "Правильный ответ": "кошка",
                        "Неверный 1": "собака",
                        "Неверный 2": "птица",
                        "Неверный 3": "мышь"
                    },
                    {
                        "Слово (DE)": "der Tisch",
                        "Правильный ответ": "стол",
                        "Неверный 1": "стул",
                        "Неверный 2": "диван",
                        "Неверный 3": "кровать"
                    },
                    {
                        "Слово (DE)": "die Welt",
                        "Правильный ответ": "мир",
                        "Неверный 1": "планета",
                        "Неверный 2": "страна",
                        "Неверный 3": "город"
                    },
                    {
                        "Слово (DE)": "das Wasser",
                        "Правильный ответ": "вода",
                        "Неверный 1": "огонь",
                        "Неверный 2": "земля",
                        "Неверный 3": "воздух"
                    },
                    {
                        "Слово (DE)": "der Apfel",
                        "Правильный ответ": "яблоко",
                        "Неверный 1": "груша",
                        "Неверный 2": "банан",
                        "Неверный 3": "апельсин"
                    },
                    {
                        "Слово (DE)": "die Lampe",
                        "Правильный ответ": "лампа",
                        "Неверный 1": "диван",
                        "Неверный 2": "окно",
                        "Неверный 3": "стул"
                    },
                    {
                        "Слово (DE)": "die Tür",
                        "Правильный ответ": "дверь",
                        "Неверный 1": "стена",
                        "Неверный 2": "крыша",
                        "Неверный 3": "пол"
                    },
                    {
                        "Слово (DE)": "das Fenster",
                        "Правильный ответ": "окно",
                        "Неверный 1": "дверь",
                        "Неверный 2": "штора",
                        "Неверный 3": "стекло"
                    },
                    {
                        "Слово (DE)": "der Stuhl",
                        "Правильный ответ": "стул",
                        "Неверный 1": "табурет",
                        "Неверный 2": "полка",
                        "Неверный 3": "шкаф"
                    }
                ]
                # Сохраняем тестовые данные локально
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                logger.info("Созданы и сохранены тестовые данные.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        # Возвращаем минимальный набор тестовых данных в случае ошибки
        data = [
            {
                "Слово (DE)": "der Hund",
                "Правильный ответ": "собака",
                "Неверный 1": "кошка",
                "Неверный 2": "мышь",
                "Неверный 3": "птица"
            }
        ]
        
    return data

# Функция для загрузки пользовательских данных
def load_user_data(user_id):
    file_path = f'user_data_{user_id}.json'
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    
    # Создаем новый профиль пользователя
    user_data = {
        "word_scores": {},      # Прогресс по словам
        "known_words": [],      # Выученные слова
        "incorrect_words": [],  # Слова с ошибками для повторения
        "current_words": []     # Текущий набор слов для изучения
    }
    
    return user_data

# Функция для сохранения пользовательских данных
def save_user_data(user_id, user_data):
    file_path = f'user_data_{user_id}.json'
    
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(user_data, file, ensure_ascii=False, indent=4)

# Функция для запуска веб-приложения
async def start_web_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    web_app = WebAppInfo(url=WEBAPP_URL)
    keyboard = [
        [InlineKeyboardButton("Открыть приложение для изучения немецкого", web_app=web_app)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Привет! Нажмите кнопку ниже, чтобы открыть приложение для изучения немецкого языка в стиле iOS:",
        reply_markup=reply_markup
    )

# Функция для начала тренировки слов (классический вариант)
async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data(user_id)
    words_data = load_data()
    
    # Если у пользователя нет списка слов для изучения или мы запрашиваем новые слова, создаем его
    if not user_data["current_words"] or context.user_data.get('reset_words', False):
        # Фильтруем только слова, которые еще не выучены
        available_words = [word for word in words_data if word["Слово (DE)"] not in user_data["known_words"]]
        
        if not available_words:
            await update.message.reply_text(
                "Поздравляю! Вы выучили все доступные слова! 🎉"
            )
            return
        
        # Выбираем 10 случайных слов для обучения (или меньше, если слов меньше 10)
        user_data["current_words"] = random.sample(available_words, min(10, len(available_words)))
        user_data["current_word_index"] = 0
        context.user_data['reset_words'] = False
    
    # Получаем текущее слово
    word_index = user_data.get("current_word_index", 0)
    
    if word_index < len(user_data["current_words"]):
        word_data = user_data["current_words"][word_index]
        
        # Отправляем вопрос с четырьмя вариантами
        question = word_data["Слово (DE)"]
        correct_answer = word_data["Правильный ответ"]
        options = [
            correct_answer, 
            word_data["Неверный 1"], 
            word_data["Неверный 2"], 
            word_data["Неверный 3"]
        ]
        random.shuffle(options)

        # Сохраняем информацию для проверки ответа
        context.user_data['correct_answer'] = correct_answer
        context.user_data['current_question'] = question
        
        # Получаем прогресс по текущему слову
        word_score = user_data["word_scores"].get(question, 0)
        
        # Отправляем клавиатуру с вариантами
        keyboard = [[option] for option in options]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"Слово {word_index + 1}/{len(user_data['current_words'])}: {question}?\n"
            f"Прогресс: {word_score}/500 баллов",
            reply_markup=reply_markup
        )
    else:
        # Все слова пройдены, предлагаем начать заново
        keyboard = [
            ["📚 Новые слова", "🔙 Вернуться в меню"],
            ["📱 Открыть приложение"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Отлично! Вы прошли все слова в этом наборе. Что дальше?",
            reply_markup=reply_markup
        )
    
    save_user_data(user_id, user_data)

# Обработчик ответа
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data(user_id)
    user_answer = update.message.text
    
    # Проверяем, есть ли в контексте сохраненный правильный ответ
    if 'correct_answer' in context.user_data and 'current_question' in context.user_data:
        correct_answer = context.user_data['correct_answer']
        current_question = context.user_data['current_question']
        
        if user_answer == correct_answer:
            # Обновляем счет для этого слова
            user_data["word_scores"][current_question] = user_data["word_scores"].get(current_question, 0) + 100
            
            await update.message.reply_text(
                f"Правильный ответ! +100 баллов! ✅\n"
                f"Общий прогресс для этого слова: {user_data['word_scores'].get(current_question, 0)}/500 баллов"
            )
            
            # Если набрали 500 баллов, помечаем слово как выученное
            if user_data["word_scores"].get(current_question, 0) >= 500:
                if current_question not in user_data["known_words"]:
                    user_data["known_words"].append(current_question)
                    await update.message.reply_text(
                        f"Поздравляем! Вы выучили слово '{current_question}'! 🎓"
                    )
                
                # Убираем это слово из текущего списка
                current_index = user_data.get("current_word_index", 0)
                if current_index < len(user_data["current_words"]):
                    user_data["current_words"].pop(current_index)
                    # Индекс не меняем, так как следующее слово "сдвинется" на текущую позицию
                else:
                    user_data["current_word_index"] = 0
        else:
            await update.message.reply_text(
                f"Неправильный ответ. Правильный: {correct_answer} ❌"
            )
            
            # Добавляем слово в список для повторения
            if current_question not in user_data["incorrect_words"]:
                user_data["incorrect_words"].append(current_question)
            
            # Переходим к следующему слову
            user_data["current_word_index"] = (user_data.get("current_word_index", 0) + 1) % len(user_data["current_words"])
        
        # Очищаем данные после проверки
        del context.user_data['correct_answer']
        del context.user_data['current_question']
        
        save_user_data(user_id, user_data)
        
        # Показываем клавиатуру с действиями
        keyboard = [
            ["📚 Ещё слово", "🔙 Вернуться в меню"],
            ["📱 Открыть приложение"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Что дальше?",
            reply_markup=reply_markup
        )
    else:
        # Если нет данных в контексте, обрабатываем как обычное сообщение
        await handle_message(update, context)

# Функция для показа статистики
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data(user_id)
    
    known_words = len(user_data["known_words"])
    incorrect_words = len(user_data["incorrect_words"])
    total_score = sum(user_data["word_scores"].values())
    
    await update.message.reply_text(
        f"📊 Ваша статистика:\n\n"
        f"🎓 Выученных слов: {known_words}\n"
        f"❌ Слов с ошибками: {incorrect_words}\n"
        f"🔢 Общий счет: {total_score} баллов"
    )
    
    # Показываем клавиатуру с действиями
    keyboard = [
        ["📚 Учить слова", "🔙 Вернуться в меню"],
        ["📱 Открыть приложение"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Что дальше?",
        reply_markup=reply_markup
    )

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем клавиатуру с основными командами
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["📊 Статистика", "📱 Открыть приложение"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Я твой бот для изучения немецкого языка 🇩🇪.\n\n"
        "Вы можете использовать классический интерфейс бота или открыть приложение с дизайном в стиле iOS!\n\n"
        "Выберите, что хочешь сделать:",
        reply_markup=reply_markup
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📚 Учить слова" or text == "📚 Новые слова" or text == "📚 Ещё слово":
        # Сбрасываем список слов для обучения, чтобы начать заново
        if text == "📚 Новые слова":
            context.user_data['reset_words'] = True
        await start_training(update, context)
    elif text == "🎯 Учить артикли":
        await update.message.reply_text("Скоро начнём тренировку по артиклям!")
    elif text == "📊 Статистика":
        await show_statistics(update, context)
    elif text == "📱 Открыть приложение":
        await start_web_app(update, context)
    elif text == "🔙 Вернуться в меню":
        await start(update, context)
    else:
        # Если это ответ на вопрос, то обрабатываем его
        await handle_answer(update, context)

def main():
    """Запуск бота"""
    # Получаем токен из .env
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", start_web_app))
    application.add_handler(CommandHandler("stats", show_statistics))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()