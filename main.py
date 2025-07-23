from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
import os

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="3 + 6", callback_data="calc_3_plus_6")],
    [InlineKeyboardButton(text="151 - 131", callback_data="calc_151_minus_131")]
])

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)

    if update.message:
        chat_id = update.message.chat.id

        await bot.send_message(
            chat_id=chat_id,
            text="я математик",
            reply_markup=keyboard
        )

    elif update.callback_query:
        callback = update.callback_query
        chat_id = callback.message.chat.id
        data = callback.data

        if data == "calc_3_plus_6":
            text = "9"
        elif data == "calc_151_minus_131":
            text = "20"
        else:
            text = "Невідома дія"

        await bot.answer_callback_query(callback.id)

        # Відправляємо відповідь
        await bot.send_message(chat_id=chat_id, text=text)

        # Приховуємо кнопки, видаляємо клавіатуру
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            reply_markup=None
        )

    return {"ok": True}
