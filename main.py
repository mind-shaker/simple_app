#==================================================== Імпорти та ініціалізація
from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncpg
import redis.asyncio as redis
from openai import AsyncOpenAI
import json

print("ТЕСТ НА ПЕРШИЙ ВХІД В БОТА")
print(f"ТЕСТ НА ПЕРШИЙ ВХІД")
#=================================================== Отримання конфігурації з середовища
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
#REDIS_URL = os.getenv("REDIS_URL")  # наприклад, redis://:password@host:port

#=================================================== Ініціалізація компонентів
bot = Bot(token=TELEGRAM_TOKEN)
app = FastAPI()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
#redis_client = None


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Отримання з'єднання з PostgreSQL" 0
async def get_connection():
    print(f"ВХІД в базу даних")
    return await asyncpg.connect(DATABASE_URL)

#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Виведення в ТЕЛЕГРАМ перекладених фраз" 0
async def send_phrase(conn, bot, chat_id, db_user_id, phrase_column: str, prefix: str = ""):
    query = f"SELECT {phrase_column} FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1"
    try:
        row = await conn.fetchrow(query, db_user_id)
        print(f"row {phrase_column}: {row}")
        text = row[phrase_column] if row and row[phrase_column] else None
        if text:
            await bot.send_message(chat_id=chat_id, text=prefix + text)
    except Exception as e:
        print(f"❌ Error fetching {phrase_column}: {e}")


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
    print(f"отримання запиту з телеграма")
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
        print("ТЕСТ НА ПЕРШИЙ ВХІД В БОТА")
        # перевірка чи існує в таблиці користувачів поточний користувач user_id в полі таблиці telegram_id. existing_user - це массив значень по користувачу
        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)

        # процедура створення нового користувача і заповнення полів telegram_id, username, full_name отриманими з телеграму даними user_id, username, full_name
        if user_id is not None:
            if not existing_user:
                await conn.execute(
                    "INSERT INTO users (telegram_id, username, full_name) VALUES ($1, $2, $3)",
                    user_id, username, full_name
                )
                await bot.send_message(chat_id=chat_id, text="👋 Welcome! You are our new user.")
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

            print(f"language_code: {language_code}")                                        
            language_code = language_code.strip().lower()
        
            # Validate the code
            if len(language_code) == 3 and language_code.isalpha() and language_code != 'sms' :
                # Save to DB
                await conn.execute(
                    "UPDATE users SET language = $1 WHERE id = $2",
                    language_code, db_user_id
                )
                await bot.send_message(chat_id=chat_id, text=f"✅ Language saved: {language_code}")


                
            else:
                #await bot.send_message(chat_id=chat_id, text=f"❌ Invalid language receive")
                pass

            mark = 1

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #//////////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО ІМЯ ///////////////////////////////////////////
        if command_value == 'name':
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

            send_phrase(conn, bot, chat_id, db_user_id, "phrase_2", "✅ " )
            
            await conn.execute(
                "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                db_user_id
            )
            mark = 1
        
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


        #//////////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО КРАЇНУ ///////////////////////////////////////////
        if command_value == 'country':
            print(f"in body country: {user_text}")
            
            messages = [
                {"role": "system", "content": "You are a country code conversion service."},
                {
                    "role": "user",
                    "content": f'Provide the ISO 3166-1 alpha-3 code for this country: "{user_text}". Return only the code, in uppercase, without additional text.'
                }
            ]
            
            # Отримуємо код країни
            country_code = await query_openai_chat(messages)
            
            print(f"country_code: {country_code}")
            country_code = country_code.strip().upper()
            
            # Перевіряємо, що це дійсний код
            if len(country_code) == 3 and country_code.isalpha():
                await conn.execute(
                    "UPDATE users SET country = $1 WHERE id = $2",
                    country_code, db_user_id
                )
    
                row = await conn.fetchrow(
                    "SELECT phrase_5 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                    db_user_id
                )
                print(f"row country_1: {row}")
                text_phrase_5 = row["phrase_5"] if row else None
                text_phrase_5="✅ "+ text_phrase_5
                await bot.send_message(chat_id=chat_id, text=text_phrase_5)
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )
            else:
                row = await conn.fetchrow(
                    "SELECT phrase_6 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                    db_user_id
                )
                text_phrase_6 = row["phrase_6"] if row else None
                text_phrase_6="✅ "+ text_phrase_6
                await bot.send_message(chat_id=chat_id, text=text_phrase_6)

            mark = 1

            


        
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


        #/////////////////////// ОБРОБКА РЕСПОНСУ на питання НАЛАШТУВАНЬ СПІВРОЗМОВНИКА //////////////////////////////////////
        if command_value == 'new_dialogue':
            print(f"in body dialogue: {user_text}")

            if user_text.lower() in ("yes", "y"):
                #автоматчичне створення випадкового співрозмовника
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
                    messages = [
                        {
                            "role": "system",
                            "content": "Ти — помічник, який створює психологічні профілі вигаданих людей."
                        },
                        {
                            "role": "user",
                            "content": f"""Згенеруй новий профіль, використовуючи структуру та формат як в наданому нижче прикладі профілю, але з новими значеннями, які логічно відповідають полям.
                    
                    Ось приклад профілю:
                    {json.dumps(profile_reference, ensure_ascii=False, indent=2)}
                    
                    У значенні ключа `difficulty_level` в новому згенерованому профілі заміни цифру на характеристику, яка відповідає тій цифрі разом з цифрою з цього списку:
                      1 — Open, with a mild spiritual inquiry
                      2 — Doubtful, searching, but with barriers
                      3 — Emotionally wounded, closed-off, critical
                      4 — Hostile or apathetic, with negative personal experience
                      5 — Provocative, aggressive, theologically well-versed
                    
                    Відповідь дай у форматі **JSON**, без жодних пояснень.
                    Без коду markdown, тільки чистий JSON."""
                        }
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
                    await conn.execute(
                        "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                        db_user_id
                    )
                else:
                    await bot.send_message(chat_id=chat_id, text="✅ Профіль характеристик Вашого співрозмовника вже існує. Продовжимо діалог.")
                    await conn.execute(
                        "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                        db_user_id
                    )
                    
                mark = 1
            else:
                row = await conn.fetchrow(
                    "SELECT phrase_7 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                    db_user_id
                )
                print(f"row seeker: {row}")
                text_phrase_7 = row["phrase_7"] if row else None
                text_phrase_7="✅ "+ text_phrase_7
                await bot.send_message(chat_id=chat_id, text=text_phrase_7)
                await conn.execute(
                    "UPDATE user_commands SET command = 'new_handle_dialogue' WHERE user_id = $1",
                    db_user_id
                )
                return {"status": "waiting_language"}




        
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #/////////////////////// ОБРОБКА РЕСПОНСУ на питання НАЛАШТУВАНЬ СПІВРОЗМОВНИКА //////////////////////////////////////
        if command_value == 'new_handle_dialogue':
            print(f"in body handle dialogue: {user_text}")

            #автоматчичне створення очикуваного співрозмовника
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

                messages = [
                    {
                        "role": "system",
                        "content": "Ти — помічник, який створює психологічні профілі вигаданих людей."
                    },
                    {
                        "role": "user",
                        "content": f"""Згенеруй новий профіль, використовуючи структуру та формат як в наданому нижче прикладі профілю, але з новими значеннями, які логічно відповідають полям.
                
                Ось приклад профілю:
                {json.dumps(profile_reference, ensure_ascii=False, indent=2)}
                
                У значенні ключа `difficulty_level` в новому згенерованому профілі заміни цифру на характеристику, яка відповідає тій цифрі разом з цифрою з цього списку:
                  1 — Open, with a mild spiritual inquiry
                  2 — Doubtful, searching, but with barriers
                  3 — Emotionally wounded, closed-off, critical
                  4 — Hostile or apathetic, with negative personal experience
                  5 — Provocative, aggressive, theologically well-versed

                При генерації полів профілю врахуй будь ласка ось ці побажання: {user_text}.

                
                Відповідь дай у форматі **JSON**, без жодних пояснень.
                Без коду markdown, тільки чистий JSON."""
                    }
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
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )
            else:
                await bot.send_message(chat_id=chat_id, text="✅ Профіль характеристик Вашого співрозмовника вже існує. Продовжимо діалог.")
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
            print(f"Тест пустої комірки мови")
     
            await conn.execute("""
                INSERT INTO user_commands (user_id, command)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
            """, db_user_id, "language")
        
            await bot.send_message(
                chat_id=chat_id,
                text="🔥 Enter your language",
                parse_mode="Markdown"
            )
            return {"status": "waiting_language"}
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #////////////////////////////// ТЕСТ комірки В ТАБЛИЦІ ПЕРЕКЛАДІВ (з миттєвим заповненням) //////////////////////////
        row = await conn.fetchrow(
            "SELECT 1 FROM translated_phrases WHERE user_id = $1 AND phrase_1 IS NOT NULL",
            db_user_id
        )
        
        if row:
            print("✅ Користувач існує і поле phrase_1 заповнене")
        else:
            print(f"Тест пустої комірки перекладу")
            print("❌ Або користувача немає, або поле language порожнє")
            #await bot.send_message(chat_id=chat_id, text=f"✅ Switching to your language of communication.")
                

                    
            # Отримуємо мову користувача з бази
            row = await conn.fetchrow("SELECT language FROM users WHERE id = $1", db_user_id)
            language = row["language"] if row else "eng"
            
            # Набір англійських фраз
            phrases = (
                "Please enter your name.", # - phrase_1 (
                "Name saved.", # - phrase_2
                "Invalid input", # - phrase_3
                "Which country are you from?", # - phrase_4
                "Country name saved.", # - phrase_5
                "Would you like me to automatically generate the characteristics of your conversation partner?", # - phrase_6
                "Please describe your conversation partner.", # - phrase_7
                "Conversation partner's profile generated.", # - phrase_8
                "Let's chat!", # - phrase_9
                "Conversation partner's profile generated.", # - phrase_10
                "Conversation partner's profile generated.", # - phrase_11
                "Conversation partner's profile generated.", # - phrase_12
                "Conversation partner's profile generated.", # - phrase_13
                "Conversation partner's profile generated.", # - phrase_14
                "Conversation partner's profile generated." # - phrase_15
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
                line.strip()
                for line in response_text.strip().split("\n")
                if line.strip()  # відкидаємо пусті рядки
            )
    
            print(f"translated_phrases : {translated_phrases}")
    
    
            # Заповнюємо до 15 елементів None, якщо менше
            translated_phrases = list(translated_phrases)
            while len(translated_phrases) < 15:
                translated_phrases.append(None)
    
    
            
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
                ON CONFLICT (user_id) DO UPDATE SET
                phrase_1 = EXCLUDED.phrase_1,
                phrase_2 = EXCLUDED.phrase_2,
                phrase_3 = EXCLUDED.phrase_3,
                phrase_4 = EXCLUDED.phrase_4,
                phrase_5 = EXCLUDED.phrase_5,
                phrase_6 = EXCLUDED.phrase_6,
                phrase_7 = EXCLUDED.phrase_7,
                phrase_8 = EXCLUDED.phrase_8,
                phrase_9 = EXCLUDED.phrase_9,
                phrase_10 = EXCLUDED.phrase_10,
                phrase_11 = EXCLUDED.phrase_11,
                phrase_12 = EXCLUDED.phrase_12,
                phrase_13 = EXCLUDED.phrase_13,
                phrase_14 = EXCLUDED.phrase_14,
                phrase_15 = EXCLUDED.phrase_15
            """, db_user_id, *translated_phrases[:15])
    
    
      
            await conn.execute(
                "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                db_user_id
            )
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #/////////////////////////////////////// ТЕСТ комірки ДЕ ВКАЗАНО ІМЯ ////////////////////////////////////////////////
        if not existing_user["name"]:
            print(f"Тест пустої комірки імя")


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


        #/////////////////////////////////////// ТЕСТ комірки ДЕ ВКАЗАНО КРАЇНУ ////////////////////////////////////////////////
        if not existing_user["country"]:
            print(f"Тест пустої комірки країни")


            await conn.execute("""
                INSERT INTO user_commands (user_id, command)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
            """, db_user_id, "country")



            row = await conn.fetchrow(
                "SELECT phrase_4 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                db_user_id
            )
            print(f"row country: {row}")
            
            text_phrase_4 = row["phrase_4"] if row else None
            text_phrase_4="🔥 "+ text_phrase_4
            await bot.send_message(
                chat_id=chat_id,
                text=text_phrase_4,
                parse_mode="Markdown"
            )
            return {"status": "waiting_country"}

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
        


        #/////////////////////////////////////// ПИТАННЯ про РУЧНЕ ВИЗНАЧЕННЯ СПІВРОЗМОВНИКА ////////////////////////////////
        if not existing_user["initial"]:
            print(f"Тест пустої комірки initial")


            await conn.execute("""
                INSERT INTO user_commands (user_id, command)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
            """, db_user_id, "new_dialogue")



            row = await conn.fetchrow(
                "SELECT phrase_6 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                db_user_id
            )
            print(f"new_dialogue: {row}")
            
            text_phrase_6 = row["phrase_6"] if row else None
            text_phrase_6="🔥 "+ text_phrase_6
            await bot.send_message(
                chat_id=chat_id,
                text=text_phrase_6,
                parse_mode="Markdown"
            )
            await conn.execute(
                "UPDATE users SET initial = $1 WHERE id = $2",
                'pss', db_user_id
            )
            return {"status": "waiting_seeker_status"}

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
        
        #/////////////////////////////////////// ПИТАННЯ про РУЧНЕ ВИЗНАЧЕННЯ СПІВРОЗМОВНИКА ////////////////////////////////
        if mark == 1:
            row = await conn.fetchrow(
                "SELECT phrase_9 FROM translated_phrases WHERE user_id = $1 ORDER BY id DESC LIMIT 1",
                db_user_id
            )
            print(f"new_dialogue: {row}")
            
            text_phrase_9 = row["phrase_9"] if row else None
            text_phrase_9="🔥 "+ text_phrase_9
            await bot.send_message(
                chat_id=chat_id,
                text=text_phrase_9,
                parse_mode="Markdown"
            )
            return {"status": "data_updated"}
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


    finally:
        await conn.close()


    return {"status": "ok"}
