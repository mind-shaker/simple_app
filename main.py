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

async def query_openrouter_chat(messages: list[dict]) -> str:
    payload = {
        "model": "mistralai/mistral-small-3.2-24b-instruct:free",
        "messages": messages
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            print("📦 payload API:", payload)
            response = await client.post(API_URL, headers=headers, json=payload)
            print("📦 JSON-відповідь від API:", response)
            response.raise_for_status()
            
            data = response.json()
            # print("📦 JSON-data:", data)
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

        # Перечитуємо користувача після оновлень
        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)

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
        if user_text.strip().lower() == "/erasure":
            await conn.execute("DELETE FROM dialogs WHERE user_id = $1", db_user_id)
            await bot.send_message(chat_id=chat_id, text="🗑️ Всі ваші повідомлення видалено з бази.")
            return

        # В іншому випадку — надсилаємо запит до ШІ
        # Надсилаємо повідомлення і зберігаємо його
        thinking_msg = await bot.send_message(chat_id=chat_id, text="🧠 Думаю...")

        # 1. Зберегти повідомлення користувача
        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at) VALUES ($1, 'user', $2, NOW())",
            db_user_id, user_text
        )

        # 1.5 Готуємо контекст останніх 10 повідомлень в одне
        # Отримуємо останні 10 повідомлень користувача
        rows = await conn.fetch(
            "SELECT role, message FROM dialogs WHERE user_id = $1 ORDER BY id ASC LIMIT 10",
            db_user_id
        )

        # Формуємо масив у форматі, який розуміє Hugging Face API
        messages = [{"role": row["role"], "content": row["message"]} for row in rows]
        
        # Додаємо нове повідомлення користувача (перед відправкою до ШІ)
        # messages.append({"role": "user", "content": user_text})
        
        # 2. Отримати відповідь від ШІ
        response_text = await query_openrouter_chat(messages)

        print("👤 response_text:", response_text)
        
        # 3. Зберегти відповідь ШІ
        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at) VALUES ($1, 'ai', $2, NOW())",
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
