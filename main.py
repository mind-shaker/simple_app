from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import asyncio

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")  # Токен бота в змінній середовища
bot = Bot(token=TOKEN)

# Клавіатура з двома кнопками
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="3 + 6", callback_data="calc_3_plus_6")],
    [InlineKeyboardButton(text="151 - 131", callback_data="calc_151_minus_131")]
])

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)

    if update.message:
        # Обробка текстового повідомлення
        chat_id = update.message.chat.id

        await bot.send_message(
            chat_id=chat_id,
            text="я математик",
            reply_markup=keyboard
        )
    elif update.callback_query:
        # Обробка натискання кнопки
        callback = update.callback_query
        chat_id = callback.message.chat.id
        data = callback.data

        if data == "calc_3_plus_6":
            text = "9"
        elif data == "calc_151_minus_131":
            text = "20"
        else:
            text = "Невідома дія"

        # Обов’язково відповідаємо на callback, щоб не було "зависання" кнопки в Telegram
        await bot.answer_callback_query(callback.id)
        await bot.send_message(chat_id=chat_id, text=text)

    return {"ok": True}


