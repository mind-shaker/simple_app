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
    
    print("🚀 Надсилаємо запит до Hugging Face...")
    print("🔑 TOKEN:", HF_TOKEN[:10] + "..." if HF_TOKEN else "❌ Немає токена")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(HF_API_URL, json=payload, headers=headers)
            print("📡 Status Code:", response.status_code)
            print("📦 Response JSON:", response.json())
            
            if response.status_code == 200:
                result = response.json()
                generated = result[0]["generated_text"]
                answer = generated.split("[/INST]")[-1].strip()
                return answer
            else:
                return f"⚠️ Hugging Face помилка: {response.status_code}"

        except Exception as e:
            print("❌ Виняток під час запиту:", str(e))
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
        print("🔥 Відправка в ШІ")
        response_text = await query_huggingface(user_text)
        print("🔥 Отримано текст від huggingface:", response_text)
        await bot.send_message(chat_id=chat_id, text=response_text)

    return {"status": "ok"}
