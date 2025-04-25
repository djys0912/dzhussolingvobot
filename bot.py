import pandas as pd
import json
import os
import logging
from dotenv import load_dotenv
load_dotenv()
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

# Функция для тренировки слов
async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words_data = load_data()  # Загружаем данные

    # Случайным образом выбираем слово для тренировки
    word = random.choice(words_data)
    
    # Отправляем вопрос с четырьмя вариантами
    question = word['Слово (DE)']
    correct_answer = word['Правильный ответ']
    options = [correct_answer, word['Неверный 1'], word['Неверный 2'], word['Неверный 3']]
    random.shuffle(options)

    # Сохраняем правильный ответ в контексте пользователя
    if not context.user_data:
        context.user_data = {}
    context.user_data['correct_answer'] = correct_answer
    context.user_data['current_question'] = question

    # Отправляем клавиатуру с вариантами
    keyboard = [[option] for option in options]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"Что означает слово: {question}?",
        reply_markup=reply_markup
    )

# Обработчик ответа
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_answer = update.message.text
    
    # Проверяем, есть ли в контексте сохраненный правильный ответ
    if context.user_data and 'correct_answer' in context.user_data:
        correct_answer = context.user_data['correct_answer']
        if user_answer == correct_answer:
            await update.message.reply_text("Правильный ответ! Отлично! ✅")
        else:
            await update.message.reply_text(f"Неправильный ответ. Правильный: {correct_answer} ❌")
        
        # После ответа предложим следующее слово
        keyboard = [
            ["📚 Еще слово", "🔙 Вернуться в меню"],
            ["📈 Статистика", "⚙️ Настройки"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Что дальше?", reply_markup=reply_markup)
        
        # Очищаем данные после проверки
        del context.user_data['correct_answer']
        del context.user_data['current_question']
    else:
        # Если нет данных в контексте, обрабатываем как обычное сообщение
        await handle_message(update, context)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем клавиатуру с основными командами
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["📈 Статистика", "⚙️ Настройки"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Я твой бот для изучения немецкого языка 🇩🇪.\n\nВыбери, что хочешь сделать:",
        reply_markup=reply_markup
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📚 Учить слова" or text == "📚 Еще слово":
        await start_training(update, context)  # Запуск тренировки
    elif text == "🎯 Учить артикли":
        await update.message.reply_text("Скоро начнём тренировку по артиклям!")
    elif text == "📈 Статистика":
        await update.message.reply_text("Твоя статистика скоро будет здесь!")
    elif text == "⚙️ Настройки":
        await update.message.reply_text("Настройки пока в разработке.")
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()