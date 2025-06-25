from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.dispatcher.webhook import SendMessage
from fastapi import FastAPI, Request
import os

BOT_TOKEN = "7795558482:AAE8WEmzTJqQkfSLKUPXjVK40QIUC2mitYg"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
app = FastAPI()

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    return SendMessage(message.chat.id, "Привіт! Я на webhook.")

@app.post("/webhook")
async def process_webhook(request: Request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return {"status": "ok"}
