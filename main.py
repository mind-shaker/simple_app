from fastapi import FastAPI, Request
from telegram import Bot
import os
import httpx
import asyncpg


DATABASE_URL = os.getenv("DATABASE_URL")  # напр.: "postgresql://user:pass@host:port/dbname"

async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

# Змінні середовища
API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()


API_URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

async def query_openrouter_chat(user_input: str) -> str:
    payload = {
        "model": "mistralai/mistral-small-3.2-24b-instruct:free",
        "messages": [
            {
                "role": "user",
                "content": user_input
            }
        ]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            # Відповідь у форматі OpenAI-like: беремо text з choices[0].message.content
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"⚠️ Помилка при запиті до OpenRouter API: {e}"

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text", "")
    from_user = message.get("from", {})

    user_id = from_user.get("id")
    username = from_user.get("username")
    first_name = from_user.get("first_name", "")
    last_name = from_user.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()

    mark = 0  # прапорець зміни даних

    conn = await get_connection()
    try:
        # Отримуємо користувача з бази
        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)

        if user_id is not None:
            if not existing_user:
                await conn.execute(
                    "INSERT INTO users (telegram_id, username, full_name) VALUES ($1, $2, $3)",
                    user_id, username, full_name
                )
                await bot.send_message(chat_id=chat_id, text="👋 Вітаю! Ви додані в систему.")
                mark = 1
                
        else:
            print("⚠️ Неможливо вставити користувача: user_id = None")
            return {"status": "skipped_null_user"}

        # Перечитуємо користувача після оновлень
        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)        

        # Обробка /start
        if user_text.strip().lower() == "/start":
            await bot.send_message(chat_id=chat_id, text="✅ Ви вже в системі. Продовжимо 👇")
            mark = 1

        # Обробка /country=
        if user_text.lower().startswith("/country="):
            country_code = user_text.split("=", 1)[1].strip().upper()
            await conn.execute(
                "UPDATE users SET country = $1 WHERE telegram_id = $2",
                country_code, user_id
            )
            await bot.send_message(chat_id=chat_id, text=f"✅ Країну збережено: {country_code}")
            mark = 1

        # Обробка /language=
        if user_text.lower().startswith("/language="):
            lang_code = user_text.split("=", 1)[1].strip().lower()
            await conn.execute(
                "UPDATE users SET language = $1 WHERE telegram_id = $2",
                lang_code, user_id
            )
            await bot.send_message(chat_id=chat_id, text=f"✅ Мову збережено: {lang_code}")
            mark = 1

        

        # Перевірка порожнього або пробільного поля country
        country = existing_user["country"]
        if not country or country.strip() == "":
            await bot.send_message(chat_id=chat_id, text="🌍 Введіть країну у форматі: `/country=UA`", parse_mode="Markdown")
            return {"status": "waiting_country"}

        # Перевірка порожнього або пробільного поля language
        language = existing_user["language"]
        if not language or language.strip() == "":
            await bot.send_message(chat_id=chat_id, text="🗣 Введіть мову у форматі: `/language=ua`", parse_mode="Markdown")
            return {"status": "waiting_language"}

        # Якщо були зміни — завершуємо обробку
        if mark == 1:
            await bot.send_message(chat_id=chat_id, text=f"Етап налаштувань завершено. Розпочинаємо діалог")
            return {"status": "data_updated"}

        db_user_id = existing_user["id"]  # внутрішній user_id у базі для подальших операцій

        # В іншому випадку — надсилаємо запит до ШІ
        # Надсилаємо повідомлення і зберігаємо його
        thinking_msg = await bot.send_message(chat_id=chat_id, text="🧠 Думаю...")

        # 1. Зберегти повідомлення користувача
        await conn.execute(
            "INSERT INTO dialogue (user_id, sender_role, message_text, timestamp) VALUES ($1, 'user', $2, NOW())",
            db_user_id, user_text
        )
        
        # 2. Отримати відповідь від ШІ
        response_text = await query_huggingface(user_text)
        
        # 3. Зберегти відповідь ШІ
        await conn.execute(
            "INSERT INTO dialogue (user_id, sender_role, message_text, timestamp) VALUES ($1, 'assistant', $2, NOW())",
            db_user_id, response_text
        )

        # Видаляємо повідомлення, якщо воно ще є
        try:
            await thinking_msg.delete()
        except Exception as e:
            # Якщо не вдалося видалити (наприклад, вже видалено) — можна проігнорувати
            pass
        await bot.send_message(chat_id=chat_id, text=response_text)

    finally:
        await conn.close()

    return {"status": "ok"}
