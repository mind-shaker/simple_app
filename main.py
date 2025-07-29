from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import json

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")
print(f"Starting bot with token: {TOKEN}")  # Відлагоджувальне повідомлення токена

bot = Bot(token=TOKEN)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    body = await request.body()
    print(f"Received raw body: {body.decode('utf-8')}")  # Виводимо вміст запиту

    try:
        update = Update.de_json(json.loads(body), bot)
    except Exception as e:
        print(f"Error parsing update: {e}")
        return {"ok": False, "error": str(e)}

    if update.callback_query:
        data = update.callback_query.data
        query = update.callback_query
        print(f"Callback query received: {data}")

        if data == "3+6":
            await bot.answer_callback_query(callback_query_id=query.id, text="9")
            print("Replied with 9")
        elif data == "151-131":
            await bot.answer_callback_query(callback_query_id=query.id, text="20")
            print("Replied with 20")
        else:
            print("Unknown callback data")
        return {"ok": True}

    if update.message:
        chat_id = update.message.chat.id  # поправив chat_id - правильно update.message.chat.id
        text = update.message.text.lower() if update.message.text else ""
        print(f"Message received from chat_id {chat_id}: {text}")

        if "математик" in text:
            keyboard = [
                [InlineKeyboardButton("3 + 6", callback_data="3+6")],
                [InlineKeyboardButton("151 - 131", callback_data="151-131")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await bot.send_message(chat_id=chat_id, text="Я математик 🧠. Обери приклад:", reply_markup=reply_markup)
            print("Sent math examples keyboard")
        else:
            await bot.send_message(chat_id=chat_id, text="Напиши слово 'математик', щоб отримати приклади.")
            print("Sent prompt to write 'математик'")

    return {"ok": True}
