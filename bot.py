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
    
    # Если у пользователя нет списка слов для изучения, создаем его
    if 'training_words' not in context.user_data:
        # Выбираем 10 случайных слов для обучения (или меньше, если слов меньше 10)
        context.user_data['training_words'] = random.sample(words_data, min(10, len(words_data)))
        context.user_data['current_word_index'] = 0
    
    # Получаем текущее слово
    word_index = context.user_data['current_word_index']
    if word_index < len(context.user_data['training_words']):
        word = context.user_data['training_words'][word_index]
        
        # Отправляем вопрос с четырьмя вариантами
        question = word['Слово (DE)']
        correct_answer = word['Правильный ответ']
        options = [correct_answer, word['Неверный 1'], word['Неверный 2'], word['Неверный 3']]
        random.shuffle(options)

        # Сохраняем правильный ответ
        context.user_data['correct_answer'] = correct_answer
        context.user_data['current_question'] = question

        # Отправляем клавиатуру с вариантами
        keyboard = [[option] for option in options]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"Слово {word_index + 1}/{len(context.user_data['training_words'])}: {question}?",
            reply_markup=reply_markup
        )
    else:
        # Все слова пройдены, предлагаем начать заново
        keyboard = [
            ["📚 Новые слова", "🔄 Повторить эти же"],
            ["🔙 Вернуться в меню"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Отлично! Ты прошел все слова в этом наборе. Что дальше?",
            reply_markup=reply_markup
        )

# Обработчик ответа
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_answer = update.message.text
    
    # Проверяем, есть ли в контексте сохраненный правильный ответ
    if 'correct_answer' in context.user_data:
        correct_answer = context.user_data['correct_answer']
        if user_answer == correct_answer:
            await update.message.reply_text("Правильный ответ! Отлично! ✅")
        else:
            await update.message.reply_text(f"Неправильный ответ. Правильный: {correct_answer} ❌")
        
        # Очищаем данные текущего вопроса
        if 'correct_answer' in context.user_data:
            del context.user_data['correct_answer']
        if 'current_question' in context.user_data:
            del context.user_data['current_question']
        
        # Увеличиваем индекс текущего слова
        context.user_data['current_word_index'] += 1
        
        # Переходим к следующему слову
        await start_training(update, context)
    else:
        # Если нет данных в контексте, обрабатываем как обычное сообщение
        await handle_message(update, context)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем более полную клавиатуру с дополнительными опциями
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["🔄 Повторение", "🧩 Составление предложений"],
        ["📊 Статистика", "⭐ Достижения"],
        ["⚙️ Настройки", "❓ Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_text(
        "Привет! Я твой бот для изучения немецкого языка 🇩🇪.\n\nВыбери, что хочешь сделать:",
        reply_markup=reply_markup
    )

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📚 Учить слова" or text == "📚 Еще слово":
        # Сбрасываем список слов для обучения, чтобы начать заново
        if 'training_words' in context.user_data:
            del context.user_data['training_words']
        await start_training(update, context)  # Запуск тренировки
    elif text == "📚 Новые слова":
        # Сбрасываем список слов для обучения, чтобы выбрать новые
        if 'training_words' in context.user_data:
            del context.user_data['training_words']
        await start_training(update, context)
    elif text == "🔄 Повторить эти же":
        # Сбрасываем только индекс, сохраняя те же слова
        context.user_data['current_word_index'] = 0
        await start_training(update, context)
    elif text == "🎯 Учить артикли":
        await update.message.reply_text("Скоро начнём тренировку по артиклям!")
    elif text == "📈 Статистика" or text == "📊 Статистика":
        await update.message.reply_text("Твоя статистика скоро будет здесь!")
    elif text == "⭐ Достижения":
        await update.message.reply_text("Здесь будут твои достижения!")
    elif text == "🔄 Повторение":
        await update.message.reply_text("Режим повторения в разработке!")
    elif text == "🧩 Составление предложений":
        await update.message.reply_text("Режим составления предложений в разработке!")
    elif text == "⚙️ Настройки":
        await update.message.reply_text("Настройки пока в разработке.")
    elif text == "❓ Помощь":
        await update.message.reply_text("Чем я могу помочь?\n\n- 📚 Учить слова: Тренировка новых слов немецкого языка\n- 🎯 Учить артикли: Тренировка артиклей немецких существительных\n- 🔄 Повторение: Повтор ранее изученных слов\n- 📊 Статистика: Твой прогресс в изучении")
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
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()