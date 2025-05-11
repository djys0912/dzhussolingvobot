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
# Импорт для работы с Supabase
from supabase import create_client, Client
import aiohttp

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_URL = "https://djys0912.github.io/dzhussolingvobot/german_app.html"

# Настройка подключения к Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://oyppivnywdzbdqmugwfp.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im95cHBpdm55d2R6YmRxbXVnd2ZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY3MjE3NzUsImV4cCI6MjA2MjI5Nzc3NX0.GspH-GCes-8d001Ox8oRao2_5jOHy1wEYlGrel5WHMI')

# ИСПРАВЛЕННАЯ инициализация Supabase
supabase_client = None

def init_supabase():
    """Инициализация Supabase клиента"""
    global supabase_client
    try:
        # Создаем клиента без дополнительных параметров
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase клиент успешно инициализирован")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации Supabase: {e}")
        return False

# Исправленная функция инициализации Supabase таблиц
def init_supabase_tables():
    global supabase_client
    if not supabase_client:
        init_supabase()
    
    try:
        # Используем синхронный вызов вместо async
        result = supabase_client.table('progress').select('*').limit(1).execute()
        logger.info("Таблица progress уже существует")
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке таблиц: {e}")
        # Если таблица не существует, можно создать её вручную в Supabase Dashboard
        return False

# Функция для синхронизации прогресса пользователя с Supabase
async def sync_progress_to_supabase(user_id, word, progress, known=False, is_error=False):
    if not str(user_id).startswith("user_"):
        user_id = f"user_{user_id}"
    """Сохраняет или обновляет прогресс в Supabase"""
    global supabase_client
    if not supabase_client:
        init_supabase()
    
    try:
        # Проверяем, существует ли уже запись
        existing = supabase_client.table('progress').select('*').eq('user_id', user_id).eq('word', word).execute()
        
        progress_data = {
            "user_id": user_id,
            "word": word,
            "progress": progress,
            "known": known,
            "is_error": is_error,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if existing.data:
            # Обновляем существующую запись
            response = supabase_client.table('progress').update(progress_data).eq('user_id', user_id).eq('word', word).execute()
        else:
            # Создаем новую запись
            response = supabase_client.table('progress').insert(progress_data).execute()
        
        logger.info(f"Прогресс для пользователя {user_id} обновлен: {word} - {progress}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при синхронизации прогресса: {e}")
        return False

# Функция для загрузки прогресса пользователя из Supabase
async def load_progress_from_supabase(user_id):
    if not str(user_id).startswith("user_"):
        user_id = f"user_{user_id}"
    """Загружает весь прогресс пользователя из Supabase"""
    global supabase_client
    if not supabase_client:
        init_supabase()
    
    try:
        response = supabase_client.table('progress').select('*').eq('user_id', user_id).execute()
        
        if response.data:
            logger.info(f"Загружен прогресс для пользователя {user_id}: {len(response.data)} записей")
            return response.data
        else:
            logger.info(f"Прогресс для пользователя {user_id} не найден")
            return []
    except Exception as e:
        logger.error(f"Ошибка при загрузке прогресса: {e}")
        return []

# Модифицированная функция загрузки пользовательских данных
async def load_user_data(user_id):
    # Сначала пробуем загрузить из Supabase
    supabase_data = await load_progress_from_supabase(user_id)
    
    if supabase_data:
        # Преобразуем данные из Supabase в формат бота
        user_data = {
            "word_scores": {},
            "known_words": [],
            "incorrect_words": [],
            "current_words": []
        }
        
        for item in supabase_data:
            word = item.get('word')
            progress = item.get('progress', 0)
            known = item.get('known', False)
            is_error = item.get('is_error', False)
            
            user_data["word_scores"][word] = progress
            
            if known:
                user_data["known_words"].append(word)
            
            if is_error:
                user_data["incorrect_words"].append(word)
        
        # Сохраняем локально для резервного копирования
        file_path = f'user_data_{user_id}.json'
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(user_data, file, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Ошибка при сохранении локальных данных: {e}")
        
        return user_data
    
    # Если нет данных в Supabase, пробуем загрузить локально
    file_path = f'user_data_{user_id}.json'
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            user_data = json.load(file)
        
        # Синхронизируем локальные данные с Supabase
        await sync_local_to_supabase(user_id, user_data)
        
        return user_data
    
    # Создаем новый профиль пользователя
    user_data = {
        "word_scores": {},
        "known_words": [],
        "incorrect_words": [],
        "current_words": []
    }
    
    return user_data

# Функция для синхронизации локальных данных с Supabase
async def sync_local_to_supabase(user_id, user_data):
    if not str(user_id).startswith("user_"):
        user_id = f"user_{user_id}"
    """Синхронизирует локальные данные пользователя с Supabase"""
    try:
        for word, progress in user_data.get("word_scores", {}).items():
            known = word in user_data.get("known_words", [])
            is_error = word in user_data.get("incorrect_words", [])
            
            await sync_progress_to_supabase(user_id, word, progress, known, is_error)
        
        logger.info(f"Локальные данные пользователя {user_id} синхронизированы с Supabase")
    except Exception as e:
        logger.error(f"Ошибка при синхронизации локальных данных: {e}")

# Модифицированная функция сохранения пользовательских данных
async def save_user_data(user_id, user_data):
    # Сохраняем локально
    file_path = f'user_data_{user_id}.json'
    
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(user_data, file, ensure_ascii=False, indent=4)
        
        # Синхронизируем с Supabase
        await sync_local_to_supabase(user_id, user_data)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных пользователя {user_id}: {e}")

# Функция для обновления конкретного слова
async def update_word_progress(user_id, word, points_earned, is_known=False, is_error=False):
    if not str(user_id).startswith("user_"):
        user_id = f"user_{user_id}"
    """Обновляет прогресс конкретного слова и синхронизирует с Supabase"""
    user_data = await load_user_data(user_id)
    
    # Обновляем прогресс
    user_data["word_scores"][word] = user_data["word_scores"].get(word, 0) + points_earned
    
    # Проверяем, выучено ли слово
    if user_data["word_scores"][word] >= 500 and word not in user_data["known_words"]:
        user_data["known_words"].append(word)
        is_known = True
    
    # Проверяем, была ли ошибка
    if is_error and word not in user_data["incorrect_words"]:
        user_data["incorrect_words"].append(word)
    
    # Сохраняем и синхронизируем
    await save_user_data(user_id, user_data)
    
    # Дополнительная синхронизация с Supabase
    await sync_progress_to_supabase(
        user_id,
        word,
        user_data["word_scores"][word],
        is_known,
        word in user_data["incorrect_words"]
    )
    
    return user_data

# Функция загрузки данных слов
def load_data():
    file_path = 'words_data.json'
    
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
                df = pd.read_csv(url)
                data = df.to_dict(orient='records')
                
                # Сохраняем данные локально для следующего использования
                with open(file_path, 'w', encoding='utf-8') as file:
                    json.dump(data, file, ensure_ascii=False, indent=4)
                logger.info("Данные загружены с Google Таблицы и сохранены локально.")
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных из Google Таблицы: {e}")
                
                # Создаем тестовые данные
                data = [
                    {
                        "Слово (DE)": "der Hund",
                        "Правильный ответ": "собака",
                        "Неверный 1": "кошка",
                        "Неверный 2": "мышь",
                        "Неверный 3": "птица"
                    },
                    {
                        "Слово (DE)": "der Tisch",
                        "Правильный ответ": "стол",
                        "Неверный 1": "стул",
                        "Неверный 2": "диван",
                        "Неверный 3": "кровать"
                    },
                    {
                        "Слово (DE)": "das Haus",
                        "Правильный ответ": "дом",
                        "Неверный 1": "квартира",
                        "Неверный 2": "офис",
                        "Неверный 3": "комната"
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
        "Привет! Я твой бот для изучения немецкого языка 🇩🇪.\n\n"
        "Вы можете использовать классический интерфейс бота или открыть приложение с дизайном в стиле iOS!\n\n"
        "Выберите, что хочешь сделать:",
        reply_markup=reply_markup
    )
    
    # Загружаем данные пользователя в фоновом режиме
    asyncio.create_task(load_user_data(user_id))
    
    logger.info(f"Ответ отправлен пользователю {update.effective_user.id}")

# Обработчик открытия веб-приложения
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

# Модифицированный обработчик начала тренировки
async def start_training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
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
            "Отлично! Вы прошли все слова в этом наборе. Что дальше?",
            reply_markup=reply_markup
        )
    
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
            # Обновляем прогресс и синхронизируем с Supabase
            user_data = await update_word_progress(user_id, current_question, 100, is_error=False)
            
            await update.message.reply_text(
                f"Правильный ответ! +100 баллов! ✅\n"
                f"Общий прогресс для этого слова: {user_data['word_scores'].get(current_question, 0)}/500 баллов"
            )
            
            # Если набрали 500 баллов, помечаем слово как выученное
            if user_data["word_scores"].get(current_question, 0) >= 500:
                if current_question not in user_data["known_words"]:
                    user_data["known_words"].append(current_question)
                    await save_user_data(user_id, user_data)
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
            
            # Обновляем прогресс и помечаем как ошибку
            user_data = await update_word_progress(user_id, current_question, 0, is_error=True)
            
            # Переходим к следующему слову
            user_data["current_word_index"] = (user_data.get("current_word_index", 0) + 1) % len(user_data["current_words"])
        
        # Очищаем данные после проверки
        del context.user_data['correct_answer']
        del context.user_data['current_question']
        
        await save_user_data(user_id, user_data)
        
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

# Модифицированный обработчик статистики
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    user_data = await load_user_data(user_id)
    
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

# Исправленный обработчик данных от веб-приложения
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные, полученные из веб-приложения"""
    try:
        user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
        
        # Проверяем, есть ли данные от веб-приложения
        if not hasattr(update.effective_message, 'web_app_data') or not update.effective_message.web_app_data:
            logger.info("Нет данных от веб-приложения")
            return
            
        web_app_data = update.effective_message.web_app_data
        data = json.loads(web_app_data.data)
        
        logger.info(f"Получены данные от веб-приложения: {data}")
        
        # Обрабатываем синхронизацию прогресса
        if data.get('type') == 'progress_sync':
            progress_data = data.get('progress', [])
            
            # Загружаем текущие данные пользователя
            user_data = await load_user_data(user_id)
            
            # Синхронизируем каждое слово
            for item in progress_data:
                word = item.get('word')
                progress = item.get('progress', 0)
                known = item.get('known', False)
                is_error = item.get('is_error', False)
                
                if word:
                    # Обновляем локальные данные
                    user_data["word_scores"][word] = progress
                    
                    if known and word not in user_data["known_words"]:
                        user_data["known_words"].append(word)
                    
                    if is_error and word not in user_data["incorrect_words"]:
                        user_data["incorrect_words"].append(word)
                    
                    # Сохраняем в Supabase
                    await sync_progress_to_supabase(
                        user_id,
                        word,
                        progress,
                        known,
                        is_error
                    )
            
            # Сохраняем обновленные данные
            await save_user_data(user_id, user_data)
            
            # Отправляем подтверждение пользователю
            await update.message.reply_text("✅ Прогресс успешно синхронизирован!")
            logger.info(f"Прогресс пользователя {user_id} успешно синхронизирован")
        
        elif data.get('type') == 'request_progress':
            # Веб-приложение запрашивает текущий прогресс
            user_data = await load_user_data(user_id)
            
            # Формируем данные для отправки
            response_data = {
                'type': 'progress_response',
                'progress': []
            }
            
            for word, progress in user_data["word_scores"].items():
                response_data['progress'].append({
                    'word': word,
                    'progress': progress,
                    'known': word in user_data["known_words"],
                    'is_error': word in user_data["incorrect_words"]
                })
            
            # Можно отправить ответ через главную кнопку (если нужно)
            logger.info(f"Отправка прогресса пользователю {user_id}: {len(response_data['progress'])} слов")
            
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при декодировании данных от веб-приложения: {e}")
        await update.message.reply_text("❌ Ошибка при обработке данных")
    except Exception as e:
        logger.error(f"Ошибка при обработке данных веб-приложения: {e}")
        await update.message.reply_text("❌ Произошла ошибка при синхронизации")

# Команда для проверки синхронизации
async def debug_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет синхронизацию данных пользователя"""
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    
    try:
        # Проверяем данные в Supabase
        supabase_data = await load_progress_from_supabase(user_id)
        
        # Проверяем локальные данные
        user_data = await load_user_data(user_id)
        
        # Выводим статистику
        message = f"🔍 Диагностика синхронизации для пользователя {user_id}:\n\n"
        message += f"📊 В Supabase: {len(supabase_data)} записей\n"
        message += f"💾 Локально: {len(user_data.get('word_scores', {}))} слов\n"
        message += f"✅ Выучено: {len(user_data.get('known_words', []))} слов\n"
        message += f"❌ С ошибками: {len(user_data.get('incorrect_words', []))} слов\n\n"
        
        # Проверяем расхождения
        local_words = set(user_data.get('word_scores', {}).keys())
        supabase_words = set(item['word'] for item in supabase_data)
        
        missing_in_supabase = local_words - supabase_words
        missing_locally = supabase_words - local_words
        
        if missing_in_supabase:
            message += f"🔄 Не синхронизировано в Supabase: {len(missing_in_supabase)} слов\n"
        
        if missing_locally:
            message += f"📥 Не найдено локально: {len(missing_locally)} слов\n"
        
        message += "\n/force_sync - принудительная синхронизация"
        
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"Ошибка при диагностике: {e}")
        await update.message.reply_text(f"❌ Ошибка при диагностике: {str(e)}")

# Команда для принудительной синхронизации
async def force_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно синхронизирует данные пользователя"""
    user_id = f"user_{update.effective_user.id}"  # ДОБАВЛЯЕМ ПРЕФИКС
    
    try:
        await update.message.reply_text("🔄 Начинаем принудительную синхронизацию...")
        
        # Загружаем данные пользователя
        user_data = await load_user_data(user_id)
        
        # Синхронизируем все слова
        synced_count = 0
        for word, progress in user_data.get("word_scores", {}).items():
            success = await sync_progress_to_supabase(
                user_id,
                word,
                progress,
                word in user_data.get("known_words", []),
                word in user_data.get("incorrect_words", [])
            )
            if success:
                synced_count += 1
            await asyncio.sleep(0.1)  # Небольшая пауза между запросами
        
        # Загружаем данные из Supabase для проверки
        supabase_data = await load_progress_from_supabase(user_id)
        
        await update.message.reply_text(
            f"✅ Синхронизация завершена!\n\n"
            f"🔄 Синхронизировано: {synced_count} слов\n"
            f"📊 В базе данных: {len(supabase_data)} записей\n"
            f"✅ Выучено: {len(user_data.get('known_words', []))} слов\n"
            f"❌ С ошибками: {len(user_data.get('incorrect_words', []))} слов"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при принудительной синхронизации: {e}")
        await update.message.reply_text(f"❌ Ошибка при синхронизации: {str(e)}")

# Принудительная синхронизация данных пользователя
async def force_sync_user_data(user_id):
    """Принудительная синхронизация данных пользователя"""
    try:
        # Загружаем данные пользователя
        user_data = await load_user_data(user_id)
        
        # Синхронизируем все слова
        for word, progress in user_data.get("word_scores", {}).items():
            await sync_progress_to_supabase(
                user_id,
                word,
                progress,
                word in user_data.get("known_words", []),
                word in user_data.get("incorrect_words", [])
            )
        
        logger.info(f"Принудительная синхронизация пользователя {user_id} завершена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при принудительной синхронизации: {e}")
        return False

# Периодическая синхронизация всех пользователей
async def periodic_sync(application):
    """Периодическая синхронизация всех пользователей"""
    while True:
        try:
            # Получаем список всех пользователей из локальных файлов
            import glob
            user_files = glob.glob('user_data_user_*.json')  # ИЗМЕНЯЕМ ПАТТЕРН
            
            for file in user_files:
                user_id = file.replace('user_data_', '').replace('.json', '')
                await force_sync_user_data(user_id)
            
            # Ждем 5 минут до следующей синхронизации
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Ошибка при периодической синхронизации: {e}")
            await asyncio.sleep(60)  # В случае ошибки ждем минуту

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"Получено сообщение: {text} от пользователя {update.effective_user.id}")

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

# Добавим функцию для установки команд
async def set_bot_commands(application):
    """Устанавливает команды бота"""
    commands = [
        ("start", "Начать работу с ботом"),
        ("app", "Открыть веб-приложение"),
        ("stats", "Показать статистику"),
        ("debug_sync", "Проверить синхронизацию"),
        ("force_sync", "Принудительная синхронизация")
    ]
    
    try:
        await application.bot.set_my_commands(commands)
        logger.info(f"Команды бота установлены: {commands}")
    except Exception as e:
        logger.error(f"Ошибка при установке команд: {e}")

def main():
    """Запуск бота"""
    # ДОБАВЛЯЕМ ДЕБАГ ЛОГИРОВАНИЕ
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Получаем токен из .env
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    logger.info(f"Запуск бота с токеном: {token[:10]}...")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Инициализируем Supabase таблицы (синхронно)
    if not init_supabase_tables():
        logger.warning("Не удалось инициализировать таблицы Supabase, бот будет работать без базы данных")
    
    # Устанавливаем команды бота
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_bot_commands(application))
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("app", start_web_app))
    application.add_handler(CommandHandler("stats", show_statistics))
    application.add_handler(CommandHandler("debug_sync", debug_sync))
    application.add_handler(CommandHandler("force_sync", force_sync))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    
    # Запускаем периодическую синхронизацию в фоне
    loop.create_task(periodic_sync(application))
    
    # Запускаем бота
    logger.info("Запуск бота...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main()