from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncpg
import redis.asyncio as redis
from openai import AsyncOpenAI
import json

DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")  # наприклад, redis://localhost або redis://:password@host:port

bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

@app.on_event("shutdown")
async def shutdown_event():
    global redis_client
    if redis_client:
        await redis_client.close()

async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

async def query_openai_chat(messages: list[dict]) -> str:
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
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

    conn = await get_connection()
    try:
        pass  # ти просив прибрати всю логіку з try
    finally:
        await conn.close()

    if redis_client and user_id:
        await redis_client.set(f"user:{user_id}:name", full_name)

    return {"status": "ok"}
