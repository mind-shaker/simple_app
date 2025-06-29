from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncpg
from openai import AsyncOpenAI

DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Новий ключ для openai

bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

async def query_openai_chat(messages: list[dict]) -> str:
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",  # або "gpt-3.5-turbo" для дешевшої моделі
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Помилка при запиті до OpenAI API: {e}"

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

    mark = 0

    conn = await get_connection()
    try:
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

        if user_text.strip().lower() == "/start":
            await bot.send_message(chat_id=chat_id, text="✅ Ви вже в системі. Продовжимо 👇")
            mark = 1

        if user_text.lower().startswith("/country="):
            country_code = user_text.split("=", 1)[1].strip().upper()
            await conn.execute("UPDATE users SET country = $1 WHERE telegram_id = $2", country_code, user_id)
            await bot.send_message(chat_id=chat_id, text=f"✅ Країну збережено: {country_code}")
            mark = 1

        if user_text.lower().startswith("/language="):
            lang_code = user_text.split("=", 1)[1].strip().lower()
            await conn.execute("UPDATE users SET language = $1 WHERE telegram_id = $2", lang_code, user_id)
            await bot.send_message(chat_id=chat_id, text=f"✅ Мову збережено: {lang_code}")
            mark = 1

        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)

        if not existing_user["country"]:
            await bot.send_message(chat_id=chat_id, text="🌍 Введіть країну: `/country=UA`", parse_mode="Markdown")
            return {"status": "waiting_country"}

        if not existing_user["language"]:
            await bot.send_message(chat_id=chat_id, text="🔥 Введіть мову: `/language=ua`", parse_mode="Markdown")
            return {"status": "waiting_language"}

        if mark == 1:
            await bot.send_message(chat_id=chat_id, text="Розпочнимо діалог")
            return {"status": "data_updated"}

        db_user_id = existing_user["id"]
        if user_text.strip().lower() == "/erasure":
            await conn.execute("DELETE FROM dialogs WHERE user_id = $1", db_user_id)
            await bot.send_message(chat_id=chat_id, text="🗑️ Всі ваші повідомлення видалено")
            return

        thinking_msg = await bot.send_message(chat_id=chat_id, text="🧠 Думаю...")

        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at) VALUES ($1, 'user', $2, NOW())",
            db_user_id, user_text
        )

        rows = await conn.fetch(
            "SELECT role, message FROM dialogs WHERE user_id = $1 ORDER BY id ASC LIMIT 10",
            db_user_id
        )
        messages = [{"role": row["role"], "content": row["message"]} for row in rows]

        response_text = await query_openai_chat(messages)

        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at) VALUES ($1, 'ai', $2, NOW())",
            db_user_id, response_text
        )

        try:
            await thinking_msg.delete()
        except:
            pass

        await bot.send_message(chat_id=chat_id, text=response_text)

    finally:
        await conn.close()

    return {"status": "ok"}
