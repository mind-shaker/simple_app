from fastapi import FastAPI, Request
import os
import telegram

# 🔑 Токен бота
TOKEN = os.getenv("BOT_TOKEN") or "тут_твій_токен"

# 🤖 Ініціалізація бота
bot = telegram.Bot(token=TOKEN)

# 🌐 FastAPI додаток
app = FastAPI()

# 📩 Обробка вхідних POST-запитів з Telegram
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if chat_id:
        bot.send_message(chat_id=chat_id, text="Зрозумів")

    return {"status": "ok"}
