import pandas as pd
import json
import os
import logging
from dotenv import load_dotenv
load_dotenv()
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random
import asyncio
from datetime import datetime

# === Firebase Admin SDK init ===
import firebase_admin
from firebase_admin import credentials, firestore

# Используем новый ключ для резервного копирования (по инструкции)
cred = credentials.Certificate("/etc/secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def load_user_data(user_id):
    # Сначала пробуем загрузить локальные данные
    file_path = f'user_data_{user_id}.json'
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                user_data = json.load(file)
            logger.info("Загружены данные из локального файла.")
        else:
            # Если локального файла нет, загружаем данные из исходного источника (например, Google Sheets)
            user_data = load_data()
            # Сохраняем в локальный файл
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(user_data, file, ensure_ascii=False, indent=4)
            logger.info("Данные загружены с Google Таблицы и сохранены локально.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        # Если возникла ошибка, создаем пустую структуру данных
        user_data = {
            "word_scores": {},
            "known_words": [],
            "incorrect_words": [],
            "current_words": [],
            "current_word_index": 0
        }
    # Попробуем загрузить резервную копию из Firebase, если локальных данных нет
    try:
        doc = db.collection("user_progress").document(user_id).get()
        if doc.exists:
            firebase_data = doc.to_dict().get("data", {})
            if firebase_data:
                logger.info(f"Загружены данные из Firebase для пользователя {user_id}")
                return firebase_data
    except Exception as e:
        logger.error(f"Ошибка при загрузке из Firebase: {e}")
    return user_data


async def save_user_data(user_id, user_data):
    """Сохраняет данные пользователя локально и резервную копию в Firebase"""
    file_path = f'user_data_{user_id}.json'
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)
        # Сохраняем резервную копию в Firebase
        await backup_to_firebase(user_id, user_data)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных пользователя {user_id}: {e}")

async def update_word_progress(user_id, word, points_earned, is_known=False, is_error=False):
    """Обновляет прогресс конкретного слова"""
    # Загружаем текущие данные пользователя
    user_data = await load_user_data(user_id)
    # Обновляем прогресс слова локально
    user_data["word_scores"][word] = user_data["word_scores"].get(word, 0) + points_earned
    # Если слово выучено (прогресс >= 500) и еще не в списке выученных, добавляем
    if user_data["word_scores"][word] >= 500 and word not in user_data["known_words"]:
        user_data["known_words"].append(word)
    # Если отметили ошибкой и слова нет в списке с ошибками, добавляем
    if is_error and word not in user_data["incorrect_words"]:
        user_data["incorrect_words"].append(word)
    # Сохраняем обновленные данные локально
    await save_user_data(user_id, user_data)
    return user_data

# Загрузка данных (например, из Google Sheets или локального источника)
def load_data():
    # ... реализация функции load_data() ...
    # Эта функция загружает исходный набор слов (например, из JSON или Google Sheets)
    # Возвращает структуру данных, аналогичную user_data
    pass

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
    
    # При старте загружаем прогресс пользователя для синхронизации в фоне
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    
    # Создаем клавиатуру с основными командами
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["📱 Открыть приложение"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Привет! Я помогу тебе выучить немецкие слова и род артиклей.\n\n"
        "Выбери действие из меню ниже:",
        reply_markup=reply_markup
    )
    # Запускаем асинхронную загрузку данных пользователя (Supabase/локально) в фоне
    asyncio.create_task(load_user_data(user_id))
    logger.info(f"Ответ отправлен пользователю {update.effective_user.id}")

# Обработчик команды /app (запуск веб-приложения)
async def start_web_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    
    # Кнопка для запуска веб-приложения (Web App на базе Telegram)
    web_app_url = os.getenv('WEB_APP_URL', 'https://example.com')  # URL вашего веб-приложения
    keyboard = [
        [InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(url=web_app_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Открываем приложение для изучения слов:", reply_markup=reply_markup)

# Модифицированный обработчик начала тренировки
async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    words_data = load_data()
    
    # Если у пользователя нет списка слов для изучения или мы запрашиваем новые слова, создаем его
    if not user_data["current_words"] or context.user_data.get('reset_words', False):
        available_words = [word for word in words_data if word["Слово (DE)"] not in user_data["known_words"]]
        # Берем случайные 10 слов (или меньше, если меньше доступно)
        user_data["current_words"] = random.sample(available_words, min(10, len(available_words)))
        user_data["current_word_index"] = 0
        context.user_data['reset_words'] = False
    
    # Формируем первое слово для изучения
    word_index = user_data.get("current_word_index", 0)
    if word_index < len(user_data["current_words"]):
        word_data = user_data["current_words"][word_index]
        question = word_data["Слово (DE)"]
        correct_answer = word_data["Артикль"]
        options = [correct_answer, *word_data["Другие варианты"]]
        random.shuffle(options)
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
        
        # Синхронизируем прогресс с Supabase после отправки слова
        await sync_progress_to_supabase(
            user_id, 
            question, 
            word_score,
            question in user_data.get("known_words", []),
            question in user_data.get("incorrect_words", [])
        )
    else:
        # Все слова пройдены, предлагаем начать заново
        keyboard = [
            ["📚 Новые слова", "🔙 Вернуться в меню"],
            ["📱 Открыть приложение"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🎉 Поздравляем, вы прошли все слова! Хотите начать заново или выбрать другие слова?",
            reply_markup=reply_markup
        )
        # Сбрасываем прогресс текущей тренировки для нового набора слов
        context.user_data['reset_words'] = True
    
    # Сохраняем обновленные данные пользователя
    await save_user_data(user_id, user_data)

# Модифицированный обработчик ответа
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    user_answer = update.message.text
    
    # Проверяем, есть ли в контексте сохраненный правильный ответ
    if 'correct_answer' in context.user_data and 'current_question' in context.user_data:
        correct_answer = context.user_data['correct_answer']
        current_question = context.user_data['current_question']
        
        if user_answer == correct_answer:
            # Ответ правильный
            await update.message.reply_text("✅ Верно! Вы получили 100 баллов.")
            # Обновляем прогресс и отмечаем слово как выученное, если набрано 500 баллов
            user_data = await update_word_progress(user_id, current_question, 100, is_error=False)
            await update.message.reply_text(
                f"Общий прогресс для этого слова: {user_data['word_scores'].get(current_question, 0)}/500 баллов"
            )
            # Если слово набрало 500 баллов, отмечаем его как выученное
            if user_data["word_scores"].get(current_question, 0) >= 500:
                if current_question not in user_data["known_words"]:
                    user_data["known_words"].append(current_question)
                    await save_user_data(user_id, user_data)
                await update.message.reply_text("🎉 Вы выучили это слово! Оно добавлено в ваш список выученных слов.")
            # Переходим к следующему слову
            current_index = user_data.get("current_word_index", 0)
            if current_index < len(user_data["current_words"]):
                user_data["current_words"].pop(current_index)
            # Сброс индекса для начала с нового слова
            user_data["current_word_index"] = 0
        else:
            # Ответ неправильный
            await update.message.reply_text(f"❌ Неверно. Правильный ответ: {correct_answer}")
            # Обновляем прогресс (0 баллов, отмечаем слово как ошибочное)
            user_data = await update_word_progress(user_id, current_question, 0, is_error=True)
            # Увеличиваем индекс текущего слова, переходим к следующему (цикл по списку слов)
            user_data["current_word_index"] = (user_data.get("current_word_index", 0) + 1) % len(user_data["current_words"])
        
        # Убираем сохраненный вопрос и ответ из контекста
        del context.user_data['correct_answer']
        del context.user_data['current_question']
        
        # Сохраняем прогресс пользователя
        await save_user_data(user_id, user_data)
        
        # После ответа отправляем новое слово, если список слов не пуст
        await start_training(update, context)
    else:
        # Если нет данных в контексте, обрабатываем как обычное сообщение
        await handle_message(update, context)

# Обработчик команды /stats (показать статистику)
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    
    known_words = len(user_data["known_words"])
    incorrect_words = len(user_data["incorrect_words"])
    total_score = sum(user_data["word_scores"].values())
    
    stats_message = (
        f"📊 Ваша статистика:\n\n"
        f"✅ Выучено слов: {known_words}\n"
        f"❌ Слов с ошибками: {incorrect_words}\n"
        f"💯 Общий счёт: {total_score} баллов"
    )
    await update.message.reply_text(stats_message)

# Обработчик данных из веб-приложения
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные, полученные из веб-приложения"""
    try:
        user_id = f"user_{update.effective_user.id}"
        # Проверяем, есть ли данные от веб-приложения
        if not hasattr(update.effective_message, 'web_app_data') or not update.effective_message.web_app_data:
            logger.info("Нет данных от веб-приложения")
            return
        # Извлекаем JSON-строку, присланную из Web App
        data = update.effective_message.web_app_data.data
        logger.info(f"Получены данные от веб-приложения: {data}")
        response_data = json.loads(data)
        # Обновляем локальные данные пользователя на основе полученных данных
        progress_list = response_data.get('progress', [])
        user_data = await load_user_data(user_id)
        for item in progress_list:
            word = item.get('word')
            progress = item.get('progress', 0)
            known = item.get('known', False)
            is_error = item.get('is_error', False)
            user_data["word_scores"][word] = progress
            if known and word not in user_data["known_words"]:
                user_data["known_words"].append(word)
            if is_error and word not in user_data["incorrect_words"]:
                user_data["incorrect_words"].append(word)
        # Сохраняем обновленные данные
        await save_user_data(user_id, user_data)
        logger.info(f"Прогресс пользователя {user_id} успешно обновлен")
        await update.message.reply_text("Данные успешно синхронизированы! ✅")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при декодировании данных от веб-приложения: {e}")
        await update.message.reply_text("Произошла ошибка при обработке данных. ❌")
    except Exception as e:
        logger.error(f"Ошибка при обработке данных веб-приложения: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении данных. ❌")


# Обработчик текстовых сообщений (для прочего текста, не команд)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"Получено сообщение: {text} от пользователя {update.effective_user.id}")
    # Здесь можно обработать произвольные текстовые сообщения, если нужно
    await update.message.reply_text("Извините, я понимаю только команды и специально предусмотренные действия.")

# Установка команд бота для интерфейса Telegram
async def set_bot_commands(application: Application):
    commands = [
        ("start", "Запустить/перезапустить бота"),
        ("app", "Открыть веб-приложение"),
        ("stats", "Показать статистику"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info(f"Команды бота установлены: {commands}")
    except Exception as e:
        logger.error(f"Ошибка при установке команд: {e}")

def main():
    """Запуск бота"""
    logging.getLogger().setLevel(logging.DEBUG)
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    logger.info(f"Запуск бота с токеном: {token[:10]}...")
    application = Application.builder().token(token).build()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_bot_commands(application))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", start_web_app))
    application.add_handler(CommandHandler("stats", show_statistics))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    logger.info("Запуск бота...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

# === Firebase backup ===
async def backup_to_firebase(user_id, user_data):
    try:
        doc_ref = db.collection("user_progress").document(user_id)
        doc_ref.set({
            "data": user_data,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        logger.info(f"Данные пользователя {user_id} успешно сохранены в Firebase.")
    except Exception as e:
        logger.error(f"Ошибка при резервном копировании в Firebase: {e}")

if __name__ == "__main__":
    main()