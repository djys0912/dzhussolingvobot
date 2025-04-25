import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📚 Учить слова", "🎯 Учить артикли"],
        ["📈 Статистика", "⚙️ Настройки"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я твой бот для изучения немецкого языка 🇩🇪.\n\nВыбери, что хочешь сделать:",
        reply_markup=reply_markup
    )

# Заглушка для обработки текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📚 Учить слова":
        await update.message.reply_text("Скоро начнём тренировку по словам!")
    elif text == "🎯 Учить артикли":
        await update.message.reply_text("Скоро начнём тренировку по артиклям!")
    elif text == "📈 Статистика":
        await update.message.reply_text("Твоя статистика скоро будет здесь!")
    elif text == "⚙️ Настройки":
        await update.message.reply_text("Настройки пока в разработке.")
    else:
        await update.message.reply_text("Пожалуйста, выбери действие из меню ниже!")

# Основной запуск бота
app = ApplicationBuilder().token("8171418523:AAEGuJ5DuIlD_WdYXaO68YgMls-g2KpDr8M").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Бот запущен...")
app.run_polling()