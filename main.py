from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import asyncio
import json

app = FastAPI()

# 🔐 Токен бота
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=BOT_TOKEN)

# 🔁 Обробка запитів від Telegram (вебхук)
@app.post("/")
async def telegram_webhook(request: Request):
    body = await request.body()
    update = Update.de_json(json.loads(body), bot)

    # Обробка callback-кнопок
    if update.callback_query:
        data = update.callback_query.data
        query = update.callback_query

        if data == "3+6":
            await bot.answer_callback_query(callback_query_id=query.id, text="9")
        elif data == "151-131":
            await bot.answer_callback_query(callback_query_id=query.id, text="20")
        return {"ok": True}

    # Обробка текстових повідомлень
    if update.message:
        chat_id = update.message.chat_id
        text = update.message.text.lower()

        if "математик" in text:
            # Відповідь і кнопки
            keyboard = [
                [InlineKeyboardButton("3 + 6", callback_data="3+6")],
                [InlineKeyboardButton("151 - 131", callback_data="151-131")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await bot.send_message(chat_id=chat_id, text="Я математик 🧠. Обери приклад:", reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=chat_id, text="Напиши слово 'математик', щоб отримати приклади.")

    return {"ok": True}
