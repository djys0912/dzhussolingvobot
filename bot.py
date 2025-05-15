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
import requests
def is_web_app_data(update: Update):
    return (
        hasattr(update.effective_message, 'web_app_data') and
        update.effective_message.web_app_data is not None
    )
# === Firebase Admin SDK init ===
import firebase_admin
from firebase_admin import credentials, firestore

# Определяем путь к ключу Firebase в зависимости от среды
if os.path.exists("/etc/secrets/firebase_key.json"):
    # Путь для сервера Render.com
    firebase_key_path = "/etc/secrets/firebase_key.json"
elif os.path.exists("/Users/aleksandrdzus/Desktop/Deusch Dzhusolingo/dzhussolingvobot/firebase_key.json"):
    # Ваш локальный путь
    firebase_key_path = "/Users/aleksandrdzus/Desktop/Deusch Dzhusolingo/dzhussolingvobot/firebase_key.json"
elif os.path.exists("firebase_key.json"):
    # Относительный путь в текущей директории
    firebase_key_path = "firebase_key.json"
else:
    # Если ключ не найден, логируем ошибку
    firebase_key_path = None

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализируем Firebase только если ключ найден
FIREBASE_ENABLED = False
db = None

if firebase_key_path:
    try:
        cred = credentials.Certificate(firebase_key_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Проверка подключения Firebase
        try:
            # Тестовая запись для проверки соединения
            test_ref = db.collection("system").document("test")
            test_ref.set({
                "timestamp": firestore.SERVER_TIMESTAMP,
                "status": "ok",
                "test": "Проверка соединения"
            })
            logger.info(f"Firebase успешно инициализирован и подключен!")
            FIREBASE_ENABLED = True
        except Exception as e:
            logger.error(f"Ошибка при тестировании подключения к Firebase: {e}")
            # Продолжаем работу без Firebase
    except Exception as e:
        logger.error(f"Ошибка при инициализации Firebase: {e}")
        # Продолжаем работу без Firebase
else:
    logger.warning("Файл ключа Firebase не найден. Firebase функции отключены.")

logger.info(f"Firebase {'ВКЛЮЧЕН' if FIREBASE_ENABLED else 'ОТКЛЮЧЕН'} - бот будет работать с {'использованием Firebase' if FIREBASE_ENABLED else 'локальным хранилищем'}")


async def load_user_data(user_id):
    """Загружает данные пользователя из локального файла или Firebase"""
    logger.info(f"[DEBUG] Начало загрузки данных для {user_id}")
    
    # Сначала пробуем загрузить локальные данные
    file_path = f'user_data_{user_id}.json'
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                user_data = json.load(file)
            logger.info(f"[DEBUG] Загружены данные из локального файла для {user_id}: {user_data}")
        else:
            # Если локального файла нет, создаем пустую структуру данных
            user_data = {
                "word_scores": {},
                "known_words": [],
                "incorrect_words": [],
                "current_words": [],
                "current_word_index": 0
            }
            logger.info(f"[DEBUG] Создана новая структура данных для пользователя {user_id}")
    except Exception as e:
        logger.error(f"[DEBUG] Ошибка при загрузке данных из локального файла: {e}")
        # Если возникла ошибка, создаем пустую структуру данных
        user_data = {
            "word_scores": {},
            "known_words": [],
            "incorrect_words": [],
            "current_words": [],
            "current_word_index": 0
        }
    
    # Если Firebase отключен, просто возвращаем локальные данные
    if not FIREBASE_ENABLED:
        logger.info(f"[DEBUG] Firebase отключен (FIREBASE_ENABLED={FIREBASE_ENABLED}), используются только локальные данные для {user_id}")
        return user_data
    
    # Пробуем загрузить данные из Firebase, если он доступен
    try:
        logger.info(f"[DEBUG] Попытка загрузки данных из Firebase для {user_id}")
        doc = db.collection("user_progress").document(user_id).get()
        logger.info(f"[DEBUG] Запрос к Firebase выполнен для {user_id}, документ существует: {doc.exists}")
        if doc.exists:
            firebase_data = doc.to_dict().get("data", {})
            if firebase_data:
                logger.info(f"[DEBUG] Загружены данные из Firebase для {user_id}: {firebase_data}")
                return firebase_data
            else:
                logger.info(f"[DEBUG] Документ существует, но поле 'data' пустое или отсутствует")
        else:
            logger.info(f"[DEBUG] Документ не существует в Firebase для {user_id}")
    except Exception as e:
        logger.error(f"[DEBUG] Ошибка при загрузке из Firebase: {e}")
    
    logger.info(f"[DEBUG] Возвращаем локальные данные для {user_id}, т.к. Firebase не вернул данные")
    return user_data


async def save_user_data(user_id, user_data):
    """Сохраняет данные пользователя локально и резервную копию в Firebase"""
    file_path = f'user_data_{user_id}.json'
    try:
        # Сохраняем локально
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)
        logger.info(f"[DEBUG] Данные сохранены локально для {user_id}: {user_data}")
        
        # Сохраняем в Firebase только если он доступен
        if FIREBASE_ENABLED:
            try:
                success = await backup_to_firebase(user_id, user_data)
                logger.info(f"[DEBUG] Результат сохранения в Firebase для {user_id}: {success}")
            except Exception as e:
                logger.error(f"[DEBUG] Ошибка при резервном копировании в Firebase: {e}")
    except Exception as e:
        logger.error(f"[DEBUG] Ошибка при сохранении данных пользователя {user_id}: {e}")


async def update_word_progress(user_id, word, points_earned, is_known=False, is_error=False):
    """Обновляет прогресс конкретного слова"""
    # Загружаем текущие данные пользователя
    user_data = await load_user_data(user_id)
    
    # Обновляем прогресс слова
    user_data["word_scores"][word] = user_data["word_scores"].get(word, 0) + points_earned
    
    # Если слово выучено (прогресс >= 500) и еще не в списке выученных, добавляем
    if user_data["word_scores"][word] >= 500 and word not in user_data["known_words"]:
        user_data["known_words"].append(word)
    
    # Если отметили ошибкой и слова нет в списке с ошибками, добавляем
    if is_error and word not in user_data["incorrect_words"]:
        user_data["incorrect_words"].append(word)
    
    # Сохраняем обновленные данные
    await save_user_data(user_id, user_data)
    return user_data


# Загрузка данных (из JSON-файла)
def load_data():
    """Загружает данные слов из JSON-файла"""
    file_path = 'words_data.json'
    
    try:
        # Если файл существует, загружаем данные
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            logger.info(f"Загружено {len(data)} слов из локального файла.")
            
            # Добавляем поля для артиклей, если их нет
            for item in data:
                if "Артикль" not in item:
                    # Извлекаем артикль из немецкого слова (например, "der Hund" -> "der")
                    word_parts = item["Слово (DE)"].split()
                    if len(word_parts) > 1 and word_parts[0] in ["der", "die", "das"]:
                        item["Артикль"] = word_parts[0]
                    else:
                        item["Артикль"] = "der"  # По умолчанию
                
                if "Другие варианты" not in item:
                    # Добавляем другие артикли для выбора
                    current = item.get("Артикль", "der")
                    item["Другие варианты"] = [a for a in ["der", "die", "das"] if a != current]
            
            return data
        else:
            # Если файла нет, пробуем загрузить из GitHub
            url = 'https://raw.githubusercontent.com/djys0912/dzhussolingvobot/main/words_data.json'
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                
                # Добавляем поля для артиклей, если их нет
                for item in data:
                    if "Артикль" not in item:
                        word_parts = item["Слово (DE)"].split()
                        if len(word_parts) > 1 and word_parts[0] in ["der", "die", "das"]:
                            item["Артикль"] = word_parts[0]
                        else:
                            item["Артикль"] = "der"
                    
                    if "Другие варианты" not in item:
                        current = item.get("Артикль", "der")
                        item["Другие варианты"] = [a for a in ["der", "die", "das"] if a != current]
                
                # Сохраняем данные локально для следующего использования
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                logger.info(f"Загружено {len(data)} слов из GitHub и сохранено локально.")
                return data
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
    
    # В случае ошибки возвращаем минимальный набор тестовых данных
    logger.info("Возвращаем тестовые данные.")
    return [
        {
            "Слово (DE)": "der Hund",
            "Правильный ответ": "собака",
            "Неверный 1": "кошка",
            "Неверный 2": "мышь",
            "Неверный 3": "птица",
            "Артикль": "der",
            "Другие варианты": ["die", "das"]
        },
        {
            "Слово (DE)": "das Haus",
            "Правильный ответ": "дом",
            "Неверный 1": "машина",
            "Неверный 2": "улица",
            "Неверный 3": "парк",
            "Артикль": "das",
            "Другие варианты": ["der", "die"]
        },
        {
            "Слово (DE)": "die Frau",
            "Правильный ответ": "женщина",
            "Неверный 1": "мужчина",
            "Неверный 2": "ребенок",
            "Неверный 3": "девочка",
            "Артикль": "die",
            "Другие варианты": ["der", "das"]
        }
    ]


# Заглушка для функции sync_progress_to_supabase (теперь используем Firebase)
async def sync_progress_to_supabase(user_id, word, progress, known=False, is_error=False):
    """Заглушка для совместимости с предыдущей версией"""
    # В новой версии мы используем Firebase вместо Supabase
    logger.debug(f"Вызов sync_progress_to_supabase игнорируется, используется Firebase")
    pass


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
    
    # При старте загружаем прогресс пользователя для синхронизации в фоне
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    
    # Создаем клавиатуру с основными командами
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["📊 Статистика", "📱 Открыть приложение"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Привет! Я помогу тебе выучить немецкие слова и род артиклей.\n\n"
        "Выбери действие из меню ниже:",
        reply_markup=reply_markup
    )
    # Запускаем асинхронную загрузку данных пользователя в фоне
    asyncio.create_task(load_user_data(user_id))
    logger.info(f"Ответ отправлен пользователю {update.effective_user.id}")


# Обработчик команды /app (запуск веб-приложения)
async def start_web_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    
    # Кнопка для запуска веб-приложения (Web App на базе Telegram)
    web_app_url = os.getenv('WEB_APP_URL', 'https://djys0912.github.io/dzhussolingvobot/german_app.html')
    keyboard = [
        [InlineKeyboardButton("Открыть приложение", web_app=WebAppInfo(url=web_app_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Открываем приложение для изучения слов:", reply_markup=reply_markup)


# Обработчик для изучения артиклей
async def start_article_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"
    user_data = await load_user_data(user_id)
    words_data = load_data()
    
    # Устанавливаем флаг, что мы изучаем артикли
    context.user_data['learning_articles'] = True
    
    # Если нет текущих слов или хотим сбросить, загружаем новые
    if not user_data.get("current_words") or context.user_data.get('reset_words', False):
        available_words = [word for word in words_data if word["Слово (DE)"] not in user_data["known_words"]]
        if not available_words:
            await update.message.reply_text("Поздравляю! Вы выучили все доступные слова! 🎉")
            return
        
        # Выбираем 10 случайных слов для обучения
        user_data["current_words"] = random.sample(available_words, min(10, len(available_words)))
        user_data["current_word_index"] = 0
        context.user_data['reset_words'] = False
    
    # Получаем текущее слово
    word_index = user_data.get("current_word_index", 0)
    
    if word_index < len(user_data["current_words"]):
        word_data = user_data["current_words"][word_index]
        question = word_data["Слово (DE)"]
        
        # Для упражнения с артиклями используем поле "Артикль"
        correct_answer = word_data["Артикль"]
        options = [correct_answer] + word_data["Другие варианты"]
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
            f"Выберите правильный артикль для слова {word_index + 1}/{len(user_data['current_words'])}:\n"
            f"{question.split(' ', 1)[1] if ' ' in question else question}\n"
            f"Прогресс: {word_score}/500 баллов",
            reply_markup=reply_markup
        )
    else:
        # Все слова пройдены, предлагаем начать заново
        keyboard = [
            ["🎯 Новые артикли", "🔙 Вернуться в меню"],
            ["📱 Открыть приложение"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🎉 Поздравляем, вы прошли все слова! Хотите начать заново?",
            reply_markup=reply_markup
        )
        # Сбрасываем прогресс текущей тренировки
        context.user_data['reset_words'] = True
    
    # Сохраняем обновленные данные пользователя
    await save_user_data(user_id, user_data)


# Модифицированный обработчик начала тренировки
async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    words_data = load_data()
    
    # Сбрасываем флаг изучения артиклей
    context.user_data['learning_articles'] = False
    
    # Если у пользователя нет списка слов для изучения или мы запрашиваем новые слова, создаем его
    if not user_data.get("current_words") or context.user_data.get('reset_words', False):
        available_words = [word for word in words_data if word["Слово (DE)"] not in user_data.get("known_words", [])]
        if not available_words:
            await update.message.reply_text("Поздравляю! Вы выучили все доступные слова! 🎉")
            return
        
        # Выбираем 10 случайных слов для обучения
        user_data["current_words"] = random.sample(available_words, min(10, len(available_words)))
        user_data["current_word_index"] = 0
        context.user_data['reset_words'] = False
    
    # Получаем текущее слово
    word_index = user_data.get("current_word_index", 0)
    
    if word_index < len(user_data["current_words"]):
        word_data = user_data["current_words"][word_index]
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
            f"Слово {word_index + 1}/{len(user_data['current_words'])}: {question}\n"
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
            "🎉 Поздравляем, вы прошли все слова! Хотите начать заново?",
            reply_markup=reply_markup
        )
        # Сбрасываем прогресс текущей тренировки
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
            
            # Переходим к следующему слову - удаляем текущее из списка
            current_index = user_data.get("current_word_index", 0)
            if current_index < len(user_data["current_words"]):
                user_data["current_words"].pop(current_index)
                # Индекс не меняем, так как следующее слово "сдвинется" на текущую позицию
                if len(user_data["current_words"]) == 0:
                    user_data["current_word_index"] = 0
            else:
                user_data["current_word_index"] = 0
        else:
            # Ответ неправильный
            await update.message.reply_text(f"❌ Неверно. Правильный ответ: {correct_answer}")
            # Обновляем прогресс (0 баллов, отмечаем слово как ошибочное)
            user_data = await update_word_progress(user_id, current_question, 0, is_error=True)
            # Увеличиваем индекс текущего слова, переходим к следующему
            user_data["current_word_index"] = (user_data.get("current_word_index", 0) + 1) % max(len(user_data["current_words"]), 1)
        
        # Убираем сохраненный вопрос и ответ из контекста
        del context.user_data['correct_answer']
        del context.user_data['current_question']
        
        # Сохраняем прогресс пользователя
        await save_user_data(user_id, user_data)
        
        # После ответа отправляем новое слово, если список слов не пуст
        if context.user_data.get('learning_articles', False):
            await start_article_training(update, context)
        else:
            await start_training(update, context)
    else:
        # Обработка текстовых команд меню
        if user_answer == "📚 Учить слова" or user_answer == "📚 Новые слова" or user_answer == "📚 Ещё слово":
            # Сбрасываем список слов для обучения, чтобы начать заново
            if user_answer == "📚 Новые слова":
                context.user_data['reset_words'] = True
            await start_training(update, context)
        elif user_answer == "🎯 Учить артикли" or user_answer == "🎯 Новые артикли":
            # Сбрасываем список слов для обучения, чтобы начать заново
            if user_answer == "🎯 Новые артикли":
                context.user_data['reset_words'] = True
            await start_article_training(update, context)
        elif user_answer == "📊 Статистика":
            await show_statistics(update, context)
        elif user_answer == "📱 Открыть приложение":
            await start_web_app(update, context)
        elif user_answer == "🔙 Вернуться в меню":
            await start(update, context)
        else:
            # Если нет данных в контексте, обрабатываем как обычное сообщение
            await handle_message(update, context)


# Обработчик команды /stats (показать статистику)
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    
    known_words = len(user_data.get("known_words", []))
    incorrect_words = len(user_data.get("incorrect_words", []))
    total_score = sum(user_data.get("word_scores", {}).values())
    
    stats_message = (
        f"📊 Ваша статистика:\n\n"
        f"✅ Выучено слов: {known_words}\n"
        f"❌ Слов с ошибками: {incorrect_words}\n"
        f"💯 Общий счёт: {total_score} баллов"
    )
    
    # Показываем клавиатуру с действиями
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["🔙 Вернуться в меню", "📱 Открыть приложение"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(stats_message, reply_markup=reply_markup)


# Обработчик данных из веб-приложения
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные, полученные из веб-приложения"""
    logger.info("handle_web_app_data TRIGGERED")
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
        # Если это запрос на получение прогресса (обратная синхронизация)
        if response_data.get('type') == 'get_progress':
            user_data = await load_user_data(user_id)
            progress = []
            # Преобразуем user_data к формату, который понимает WebApp
            for word, prog in user_data.get('word_scores', {}).items():
                progress.append({
                    'word': word,
                    'progress': prog,
                    'known': word in user_data.get('known_words', []),
                    'is_error': word in user_data.get('incorrect_words', [])
                })
            # Отправляем прогресс обратно как сообщение
            await update.message.reply_text(f'PROGRESS_DATA::{json.dumps(progress)}')
            logger.info(f"Отправлен прогресс пользователю {user_id} по запросу get_progress")
            return
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
        logger.info(f"Прогресс пользователя {user_id} успешно обновлен из web-app")
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
    
    # Проверяем, является ли сообщение командой меню
    await handle_answer(update, context)


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


# === Firebase backup ===
async def backup_to_firebase(user_id, user_data):
    """Создает резервную копию данных пользователя в Firebase"""
    if not FIREBASE_ENABLED:
        logger.info(f"[DEBUG] Firebase отключен (FIREBASE_ENABLED={FIREBASE_ENABLED}), резервное копирование пропущено для {user_id}")
        return False
    
    try:
        logger.info(f"[DEBUG] Попытка сохранения в Firebase для {user_id}, данные: {user_data}")
        doc_ref = db.collection("user_progress").document(user_id)
        doc_ref.set({
            "data": user_data,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        logger.info(f"[DEBUG] Данные успешно сохранены в Firebase для {user_id}")
        
        # Проверка сохранения - сразу пытаемся прочитать
        check_doc = doc_ref.get()
        if check_doc.exists:
            logger.info(f"[DEBUG] Проверка: документ существует после сохранения")
        else:
            logger.warning(f"[DEBUG] Проверка: документ НЕ существует после сохранения!")
            
        return True
    except Exception as e:
        logger.error(f"[DEBUG] Ошибка при резервном копировании в Firebase: {e}")
        return False


def main():
    """Запуск бота"""
    logging.getLogger().setLevel(logging.INFO)
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    logger.info(f"Запуск бота с токеном: {token[:10]}...")
    application = Application.builder().token(token).build()
    
    # Устанавливаем команды бота
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_bot_commands(application))
    
    # Регистрируем обработчики
    application.add_handler(MessageHandler(is_web_app_data, handle_web_app_data))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", start_web_app))
    application.add_handler(CommandHandler("stats", show_statistics))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Запуск бота...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    main()