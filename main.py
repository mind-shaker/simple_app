from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncpg
from openai import AsyncOpenAI
import json

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
        print("📦 messages:", messages)

        response = await openai_client.chat.completions.create(
            model="gpt-4o",  # або "gpt-3.5-turbo" для дешевшої моделі
            messages=messages
        )
        print("📦 response:", response)
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
            # Якщо профіль вже є, пропускаємо створення
            db_user_id = existing_user["id"] if existing_user else (await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id))["id"]
            existing_profile = await conn.fetchrow("SELECT * FROM simulated_personas WHERE user_id = $1", db_user_id)
            if not existing_profile:
    
                init_msg = await bot.send_message(chat_id=chat_id, text="✅ ініціалізація характеристик Вашого співрозмовника..")
                profile_reference = {
                      "name": "Mariam",
                      "age": 24,
                      "country": "Egypt",
                      "difficulty_level": "1–5",
                      "religious_context": "muslim",
                      "personality": "Skeptical but emotionally open",
                      "barriers": ["God and suffering", "trust in religion"],
                      "openness": "Medium",
                      "goal": "To see if God is real and personal",
                      "big_five_traits": {
                            "openness": "high",
                            "conscientiousness": "medium",
                            "extraversion": "low",
                            "agreeableness": "medium",
                            "neuroticism": "high"
                      },
                      "temperament": "Melancholic",
                      "worldview_and_values": ["Humanism", "Skepticism"],
                      "beliefs": ["Religion is man-made", "God may exist but is distant"],
                      "motivation_and_goals": ["Find meaning after loss", "Reconnect with hope"],
                      "background": "Grew up in nominal faith, lost friend in accident",
                      "erikson_stage": "Young adulthood — Intimacy vs. Isolation",
                      "emotional_intelligence": "Moderate",
                      "thinking_style": "Analytical with emotional interference",
                      "biological_factors": ["Sleep-deprived", "Hormonal imbalance"],
                      "social_context": ["Urban Egyptian culture", "Peers secular"],
                      "enneagram": "Type 4 — Individualist",
                      "disc_profile": "C — Conscientious",
                      "stress_tolerance": "Low",
                      "self_image": "Feels broken, searching for healing",
                      "cognitive_biases": ["Confirmation bias", "Negativity bias"],
                      "attachment_style": "Anxious-preoccupied",
                      "religion": "Nominal Christian",
                      "trauma_history": "Friend's death in accident — unresolved",
                      "stress_level": "High",
                      "habits": ["Night owl", "Avoids social events"],
                      "why_contacted_us": "Saw Christian video that made her cry",
                      "digital_behavior": ["Active on Instagram", "Searches for spiritual content"],
                      "peer_pressure": ["Friends mock faith"],
                      "attachment_history": "Emotionally distant parents (based on Bowlby theory)",
                      "culture": "Middle Eastern / Egyptian",
                      "neuroprofile": "Sensitive limbic response",
                      "meta_programs": ["Away-from motivation", "External validation"],
                      "philosophical_views": ["Existentialism", "Skepticism"]
                }
                system_prompt = f"""
                Ти — помічник, який створює психологічні профілі вигаданих людей.  
                Ось приклад профілю, на основі якого потрібно згенерувати схожий профіль, але з іншими значеннями:  
                {json.dumps(profile_reference, ensure_ascii=False, indent=2)}

                Згенеруй новий профіль, використовуючи подібну структуру та формат, але з новими значеннями, які логічно відповідають полям.  
                Поле difficulty_level має бути одним із: 
                  1 — Відкритий, з легким духовним запитом  
                  2 — Сумніваючийся, шукає, але з бар'єрами  
                  3 — Емоційно травмований, закритий, критичний  
                  4 — Ворожий або апатичний, з негативним особистим досвідом  
                  5 — Провокативний, агресивний, теологічно підкований

                Відповідь дай у форматі JSON, без жодних пояснень.
                Без коду markdown, тільки JSON.
                """
                messages = [
                    {"role": "system", "content": system_prompt}
                ]
                response = await query_openai_chat(messages=messages)
                
                # Парсимо json відповідь від чату
                try:
                    persona = json.loads(response)
                except Exception as e:
                    await bot.send_message(chat_id=chat_id, text=f"❌ Помилка парсингу профілю: {e}")
                    return {"status": "error_parsing_profile"}

                # Вставляємо в базу
                await conn.execute(
                    """
                    INSERT INTO simulated_personas (
                        user_id, name, age, country, difficulty_level, religious_context, personality,
                        barriers, openness, goal, big_five_traits, temperament, worldview_and_values,
                        beliefs, motivation_and_goals, background, erikson_stage, emotional_intelligence,
                        thinking_style, biological_factors, social_context, enneagram, disc_profile,
                        stress_tolerance, self_image, cognitive_biases, attachment_style, religion,
                        trauma_history, stress_level, habits, why_contacted_us, digital_behavior,
                        peer_pressure, attachment_history, culture, neuroprofile, meta_programs, philosophical_views
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, $17, $18,
                        $19, $20, $21, $22, $23,
                        $24, $25, $26, $27, $28,
                        $29, $30, $31, $32, $33,
                        $34, $35, $36, $37, $38, $39
                    )
                    """,
                    db_user_id,
                    persona.get("name"),
                    persona.get("age"),
                    persona.get("country"),
                    persona.get("difficulty_level"),
                    persona.get("religious_context"),
                    persona.get("personality"),
                    persona.get("barriers"),
                    persona.get("openness"),
                    persona.get("goal"),
                    json.dumps(persona.get("big_five_traits")),
                    persona.get("temperament"),
                    persona.get("worldview_and_values"),
                    persona.get("beliefs"),
                    persona.get("motivation_and_goals"),
                    persona.get("background"),
                    persona.get("erikson_stage"),
                    persona.get("emotional_intelligence"),
                    persona.get("thinking_style"),
                    persona.get("biological_factors"),
                    persona.get("social_context"),
                    persona.get("enneagram"),
                    persona.get("disc_profile"),
                    persona.get("stress_tolerance"),
                    persona.get("self_image"),
                    persona.get("cognitive_biases"),
                    persona.get("attachment_style"),
                    persona.get("religion"),
                    persona.get("trauma_history"),
                    persona.get("stress_level"),
                    persona.get("habits"),
                    persona.get("why_contacted_us"),
                    persona.get("digital_behavior"),
                    persona.get("peer_pressure"),
                    persona.get("attachment_history"),
                    persona.get("culture"),
                    persona.get("neuroprofile"),
                    persona.get("meta_programs"),
                    persona.get("philosophical_views"),
                )
                await init_msg.delete()
                await bot.send_message(chat_id=chat_id, text="✅ Профіль Вашого співрозмовника згенеровано і збережено.")    
            else:
                await bot.send_message(chat_id=chat_id, text="✅ Профіль характеристик Вашого співрозмовника вже існує. Продовжимо діалог.")
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

        if user_text.strip().lower() == "/erasure_profile":
            # Очищення всієї таблиці simulated_personas
            await conn.execute("TRUNCATE TABLE simulated_personas;")
            
            # Можна додати ще видалення повідомлень користувача, якщо потрібно
            # await conn.execute("DELETE FROM dialogs WHERE user_id = $1", db_user_id)
            
            await bot.send_message(chat_id=chat_id, text="🗑️ Таблиця з профілями успішно очищена")
            return

        thinking_msg = await bot.send_message(chat_id=chat_id, text="🧠 Думаю...")

        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at) VALUES ($1, 'user', $2, NOW())",
            db_user_id, user_text
        )

        rows = await conn.fetch(
            "SELECT role, message FROM dialogs WHERE user_id = $1 ORDER BY id DESC LIMIT 10",
            db_user_id
        )
        rows = list(reversed(rows))

        
        user_messages = [
            {
                "role": "assistant" if row["role"] == "ai" else row["role"],
                "content": row["message"]
            }
            for row in rows
        ]

        print("📦 user_id:", user_id)
        # Витягнути профіль із бази для користувача (припустимо, user_id)
        profile_row = await conn.fetchrow("SELECT * FROM simulated_personas WHERE user_id = $1", user_id)
        if not profile_row:
            # Якщо профілю немає, можеш повернути порожній список або дефолтний профіль
            print("📦 profile is empty:")
            profile_content = "{}"
        else:
            # Припустимо, що профіль у таблиці збережений у полі profile_json у вигляді JSON рядка
            profile_content = profile_row["profile_json"]
            print("📦 profile_content:", profile_content)
        
        # Формуємо системне повідомлення з профілем
        system_message = {
            "role": "system",
            "content": f"Assistant profile for this session:\n{profile_content}"
        }
        
        # Далі формуємо список повідомлень, додаємо system_message спочатку, потім user_messages
        messages = [system_message] + user_messages

    
        # messages = [{"role": row["role"], "content": row["message"]} for row in rows]
        # messages = [{'role': 'user', 'content': user_text}]

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
