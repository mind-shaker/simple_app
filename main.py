from fastapi import FastAPI, Request
from telegram import Bot
import os
import httpx

HF_TOKEN = os.getenv("HF_TOKEN")
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

bot = Bot(token=TOKEN)
app = FastAPI()

async def query_huggingface(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": f"[INST] {prompt} [/INST]"}

    async with httpx.AsyncClient() as client:
        response = await client.post(HF_API_URL, json=payload, headers=headers)

    try:
        result = response.json()
        generated = result[0]["generated_text"]
        answer = generated.split("[/INST]")[-1].strip()
        return answer
    except Exception:
        return "На жаль, щось пішло не так 😔"

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()


    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text", "")
    # 🟡 Ось тут виводимо повний JSON запиту від Telegram:
    print("🔥 Отримано текст від Telegram:", user_text)

    if chat_id and user_text:
        response_text = await query_huggingface(user_text)
        await bot.send_message(chat_id=chat_id, text=response_text)

    return {"status": "ok"}
