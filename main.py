from fastapi import FastAPI, Request
from telegram import Bot

TOKEN ="7795558482:AAE8WEmzTJqQkfSLKUPXjVK40QIUC2mitYg"

bot = Bot(token=TOKEN)
app = FastAPI()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if chat_id:
        await bot.send_message(chat_id=chat_id, text="Зрозумів")

    return {"status": "ok"}
