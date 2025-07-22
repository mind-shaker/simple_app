from fastapi import FastAPI, Request
from telegram import Bot
import os



TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

app = FastAPI()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if chat_id:
        await bot.send_message(chat_id=chat_id, text="Привіт!")

    return {"status": "ok"}
