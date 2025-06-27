from fastapi import FastAPI, Request
from telegram import Bot
import os
import httpx

# Змінні середовища
HF_TOKEN = os.getenv("HF_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

API_URL = "https://router.huggingface.co/novita/v3/openai/chat/completions"
MODEL_ID = "minimaxai/minimax-m1-80k"

bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()

# 🧠 Звернення до Hugging Face
async def query_huggingface(user_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "model": MODEL_ID
    }

    print("🚀 Надсилаємо запит до Hugging Face...")
    print("🔑 TOKEN:", HF_TOKEN[:10] + "..." if HF_TOKEN else "❌ Немає токена")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(API_URL, headers=headers, json=payload)
            print("📡 Status Code:", response.status_code)

            if response.status_code == 200:
                result = response.json()
                message = result["choices"][0]["message"]
                full_content = message.get("content", "")

                if '</think>' in full_content:
                    reply = full_content.split('</think>')[-1].strip()
                else:
                    reply = full_content.split('\n\n')[-1].strip()

                return reply
            else:
                print("⚠️ HuggingFace response:", response.text)
                return f"⚠️ Hugging Face помилка: {response.status_code}"

        except Exception as e:
            print("❌ Виняток під час запиту:", str(e))
            return "На жаль, щось пішло не так 😔"

# 📩 Обробка запитів Telegram
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text", "")

    print("🔥 Отримано текст від Telegram:", user_text)

    if chat_id and user_text:
        print("🔥 Відправка в ШІ")
        response_text = await query_huggingface(user_text)
        print("🔥 Отримано текст від huggingface:", response_text)
        await bot.send_message(chat_id=chat_id, text=response_text)

    return {"status": "ok"}
