#==================================================== Імпорти та ініціалізація
from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncpg
import redis.asyncio as redis
from openai import AsyncOpenAI
import json


#=================================================== Отримання конфігурації з середовища
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")  # наприклад, redis://:password@host:port

#=================================================== Ініціалізація компонентів
bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
redis_client = None

#=================================================== Події запуску
@app.on_event("startup")
async def startup_event():
    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await redis_client.ping()
        print("[REDIS] Підключення успішне!")
    except Exception as e:
        print(f"[REDIS] Помилка підключення: {e}")

#=================================================== Події завершення
@app.on_event("shutdown")
async def shutdown_event():
    global redis_client
    if redis_client:
        await redis_client.close()
        print("[REDIS] Підключення закрите.")

#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Отримання з'єднання з PostgreSQL" 0
async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Виклик OpenAI API"
async def query_openai_chat(messages: list[dict]) -> str:
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Помилка при запиті до OpenAI API: {e}"

#=================================================== Обробка Telegram webhook
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
    #-------------------------- Робота з базою (вилучено):
    conn = await get_connection() #++++++++++++++++++++++ ВИКЛИК ФУНКЦІЇ "Отримання з'єднання з PostgreSQL" 0 +++++++++++++++++++
    try:
        #///////////////////////////////////////// ТЕСТ НА ПЕРШИЙ ВХІД В БОТА //////////////////////////////////////////////
        # перевірка чи існує в таблиці користувачів поточний користувач user_id в полі таблиці telegram_id. existing_user - це массив значень по користувачу
        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)

        # процедура створення нового користувача і заповнення полів telegram_id, username, full_name отриманими з телеграму даними user_id, username, full_name
        if user_id is not None:
            if not existing_user:
                await conn.execute(
                    "INSERT INTO users (telegram_id, username, full_name) VALUES ($1, $2, $3)",
                    user_id, username, full_name
                )
                await bot.send_message(chat_id=chat_id, text="👋 Welcome! You are our new user.\nTo set up your profile, please answer a few questions.")
                mark = 1
        else:
            print("⚠️ Неможливо вставити користувача: user_id = None")
            return {"status": "skipped_null_user"}
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        db_user_id = existing_user["id"] if existing_user else (await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id))["id"]


        command_value = await conn.fetchval(
            "SELECT command FROM user_commands WHERE user_id = $1",
            db_user_id
        )
        print(f"Current command: {command_value}")


        #////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО МОВУ СПІЛКУВАННЯ ////////////////////////////////////
        if command_value == 'language':
            print(f"in body language")

            messages = [
                {"role": "system", "content": "You are a language conversion service."},
                {
                    "role": "user",
                    "content": f'Provide the ISO 639-2 three-letter code for this language: "{user_text}". Return only the code, without additional words.'
                }
            ]
        
            # Get response from OpenAI in English
            language_code = await query_openai_chat(messages)
            language_code = language_code.strip().lower()
        
            # Validate the code
            if len(language_code) == 3 and language_code.isalpha():
                # Save to DB
                await conn.execute(
                    "UPDATE users SET language = $1 WHERE id = $2",
                    language_code, db_user_id
                )
                await bot.send_message(chat_id=chat_id, text=f"✅ Language saved: {language_code}\nSwitching to your language of communication.")


                # Отримуємо мову користувача з бази
                row = await conn.fetchrow("SELECT language FROM users WHERE id = $1", db_user_id)
                language = row["language"] if row else "Ukrainian"
                
                # Набір англійських фраз
                phrases = (
                    "Please enter your name.",
                    "Name saved.",
                    "Invalid input",
                    "Which country are you from?",
                    "Country name saved.",
                    "Would you like me to automatically generate the characteristics of your conversation partner?",
                    "Please describe your conversation partner.",
                    "Conversation partner's profile generated.",
                    "Let's chat!"
                )
                




                                
                # Формуємо промпт
                prompt = (
                    f"Translate the following English phrases into {language}. "
                    "Return only the translations, one per line, in the same order. "
                    "Do not include the original English text, any explanations, or formatting.\n\n" +
                    "\n".join(phrases)
                )
                
                # Повідомлення для OpenAI
                messages = [
                    {"role": "system", "content": "You are a translation engine. Respond with only the translated phrases, no explanations, no original text, and no formatting."},
                    {"role": "user", "content": prompt}
                ]



                
                # Відправляємо запит
                response_text = await query_openai_chat(messages)

                print(f"Text_from_GPT : {response_text}")
                
                # Розбираємо результат у кортеж
                translated_phrases = tuple(
                    line[2:].strip()
                    for line in response_text.strip().split("\n")
                    if line.startswith("- ")
                )

                # Заповнюємо до 15 елементів None, якщо менше
                translated_phrases = list(translated_phrases)
                while len(translated_phrases) < 15:
                    translated_phrases.append(None)


                # Вивід у Telegram
                #for phrase in translated_phrases:
                #    if phrase:  # пропускаємо None
                #        await bot.send_message(chat_id=chat_id, text=phrase)

                
                # Внесення у таблицю translated_phrases (решта фраз — NULL)
                await conn.execute("""
                    INSERT INTO translated_phrases (
                        user_id,
                        phrase_1, phrase_2, phrase_3, phrase_4, phrase_5,
                        phrase_6, phrase_7, phrase_8, phrase_9, phrase_10,
                        phrase_11, phrase_12, phrase_13, phrase_14, phrase_15
                    ) VALUES (
                        $1, $2, $3, $4, $5,
                        $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16
                    )
                """, db_user_id, *translated_phrases[:15])


          
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )
            else:
                await bot.send_message(chat_id=chat_id, text=f"❌ Invalid language receive")

            mark = 1

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #//////////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО ІМЯ ///////////////////////////////////////////
        if command_value == 'name':
            print(f"in body name")
            print(f"in body name: {user_text}")
            await conn.execute(
                "UPDATE users SET name = $1 WHERE id = $2",
                user_text, db_user_id
            )

            row = await conn.fetchrow(
                "SELECT phrase_2 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                db_user_id
            )
            print(f"row name_1: {row}")
            text_phrase_2 = row["phrase_2"] if row else None
            text_phrase_2="✅ "+ text_phrase_2
            await bot.send_message(chat_id=chat_id, text=text_phrase_2)
            await conn.execute(
                "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                db_user_id
            )
            mark = 1
        
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)
        print(f"existing_user: {existing_user}")

        #=========================================== ФУНКЦІЇ ПОШУКУ НЕВИЗНАЧЕНИХ ХАРАКТЕРИСТИК =============================

        #////////////////////////////// ТЕСТ комірки ПРО МОВУ СПІЛКУВАННЯ ////////////////////////////////////
        if not existing_user["language"]:
            await conn.execute("""
                INSERT INTO user_commands (user_id, command)
                VALUES ($1, $2)
            """, db_user_id, "language")
            await bot.send_message(
                chat_id=chat_id,
                text="🔥 Enter your language",
                parse_mode="Markdown"
            )
            return {"status": "waiting_language"}

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #/////////////////////////////////////// ТЕСТ комірки ДЕ ВКАЗАНО ІМЯ ////////////////////////////////////////////////
        if not existing_user["name"]:


            await conn.execute("""
                INSERT INTO user_commands (user_id, command)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
            """, db_user_id, "name")



            row = await conn.fetchrow(
                "SELECT phrase_1 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                db_user_id
            )
            print(f"row name: {row}")
            
            text_phrase_1 = row["phrase_1"] if row else None
            text_phrase_1="🔥 "+ text_phrase_1
            await bot.send_message(
                chat_id=chat_id,
                text=text_phrase_1,
                parse_mode="Markdown"
            )
            return {"status": "waiting_name"}

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


    finally:
        await conn.close()
    #-------------------------- Робота з Redis:
    if redis_client and user_id:
        # Записуємо у Redis
        await redis_client.set(f"user:{user_id}:name", full_name)
        # Читаємо назад і виводимо у консоль
        saved_name = await redis_client.get(f"user:{user_id}:name")
        print(f"[REDIS] user:{user_id}:name → {saved_name}")

    return {"status": "ok"}
