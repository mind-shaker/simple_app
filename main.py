#==================================================== Імпорти та ініціалізація
from fastapi import FastAPI, Request
from telegram import Bot
import os
import asyncpg
import redis.asyncio as redis
from openai import AsyncOpenAI
import json
import asyncio

print("ТЕСТ НА ПЕРШИЙ ВХІД В БОТА")

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
ADMIN_IDS = [231319580]  # заміни на свій Telegram ID

#=================================================== ДЕКЛАРАЦІЯ АДМІНСЬКОЇ ФУНКЦІЇ "Отримання балансу" 0
def get_balance():
    # Повертає значення з бази, API чи де в тебе зберігається баланс
    return 17.42

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
            feedback = await bot.send_message(chat_id=chat_id, text=prefix + text)
            return feedback
    except Exception as e:
        print(f"❌ Error fetching {phrase_column}: {e}")


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Збільшення лічильника повідомлень" 0
async def increment_message_count(conn, db_user_id):
    # Знаходимо ID останнього діалогу користувача
    row_id = await conn.fetchrow("""
        SELECT id FROM dialogues_stat
        WHERE user_id = $1
        ORDER BY started_at DESC
        LIMIT 1
    """, db_user_id)

    if not row_id:
        print("❌ No dialogue found for this user.")
        return None

    dialogue_id = row_id["id"]

    # Оновлюємо лічильник повідомлень і повертаємо його
    row = await conn.fetchrow("""
        UPDATE dialogues_stat
        SET message_count = message_count + 1
        WHERE id = $1
        RETURNING message_count
    """, dialogue_id)

    if row:
        message_count = row["message_count"]
        print(f"✅ Updated message_count: {message_count}, dialogue_id: {dialogue_id}")
        return message_count, dialogue_id
    else:
        print("⚠️ Dialogue ID found, but failed to update message_count.")
        return None


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "РЕЗЮМУВАННЯ від чату GPT" 0
async def summarize_dialogue(conn, dialogue_id, chat_id, db_user_id):
    # Витягнути всі повідомлення діалогу
    rows = await conn.fetch(
        "SELECT role, message FROM dialogs WHERE id_dialogue = $1 ORDER BY created_at ASC",
        dialogue_id
    )

    # Формуємо текст діалогу
    dialogue_text = "\n".join([f"{row['role'].capitalize()}: {row['message']}" for row in rows])


    row = await conn.fetchrow("SELECT language FROM users WHERE id = $1", db_user_id)
    if row:
        language = row["language"]
    else:
        language = 'eng'  # або значення за замовчуванням

    # Системний prompt із роллю психолога
    system_prompt = {
        "role": "system",
        "content": "You are an expert psychologist. Analyze the following dialogue carefully.Reply in the language specified by ISO 639-2: {language}"
    }

    # User prompt з проханням про резюмування
    user_prompt = {
        "role": "user",
        "content": (
            "Please summarize this conversation, focusing on whether openness was observed in the interlocutors during the dialogue."
            "How appropriate and non-intrusive were my attempts to engage the person in faith in God, and were these attempts successful?"
            "Was I able to lead the person to reflect on the topic of faith in God and following Him?\n\n"
            f"Dialogue:\n{dialogue_text}"
        )
    }

    messages = [system_prompt, user_prompt]

    # Виклик OpenAI API (припускаю, що є твоя функція query_openai_chat)
    summary = await query_openai_chat(messages)

    # Відправка у Telegram
    await bot.send_message(chat_id=chat_id, text=summary)

    return summary




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


        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
        #//////////////////////////////////////////// ОБРОБКА АДМІНСЬКИХ КОМАНД ////////////////////////////////////////////
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
        if text == "/status":
            if user_id not in ADMIN_IDS:
                await bot.send_message(chat_id=chat_id, text="У вас немає прав.")
                return {"ok": True}
    
            mem_used = 252451
            bal = get_balance()
            await bot.send_message(chat_id=chat_id,
                                   text=f"Використано памʼяті: {mem_used} MB\nБаланс: {bal} грн")
    
        return {"ok": True}
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

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
            if len(language_code) == 3 and language_code.isalpha() and language_code != 'sms' and language_code != 'xxx':
                # Save to DB
                await conn.execute(
                    "UPDATE users SET language = $1 WHERE id = $2",
                    language_code, db_user_id
                )
                #await bot.send_message(chat_id=chat_id, text=f"✅ Language saved: {language_code}")
                
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )

                
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

            #await send_phrase(conn, bot, chat_id, db_user_id, "phrase_2", "✅ ")

        
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
    
                #await send_phrase(conn, bot, chat_id, db_user_id, "phrase_5", "✅ ")
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )
            else:
                await send_phrase(conn, bot, chat_id, db_user_id, "phrase_3", "✅ ")

            mark = 1

            


        
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
                
        
        
        #/////////////////////////////////// ОБРОБКА ПЕРЕРИВАННЯ ПОТОЧНОГО ДІАЛОГУ //////////////////////////////////////////
        if user_text == "/new":
            # Знаходимо ID останнього діалогу користувача
            row_id = await conn.fetchrow("""
                SELECT id FROM dialogues_stat
                WHERE user_id = $1
                ORDER BY started_at DESC
                LIMIT 1
            """, db_user_id)
        
            if not row_id:
                print("❌ No dialogue found for this user.")
                return None
        
            dialogue_id = row_id["id"]

            row = await conn.fetchrow(
                "SELECT message_count FROM dialogues_stat WHERE id = $1",
                dialogue_id
            )
            if row:
                message_count = row["message_count"]
                print(f"📨 message_count for dialogue {dialogue_id}: {message_count}")
            else:
                print(f"❌ Dialogue with id {dialogue_id} not found.")
                return None

            await bot.send_message(chat_id=chat_id, text=" Vy vyjavyly bazannya perervaty potocny dialog stvoryvshy novy")
            if message_count >= 30:
                await bot.send_message(chat_id=chat_id, text="👋 U vas dostatno povidomlen dlya rezjumuvannya. Bazaete rezyumuvaty potochny dialog?")
                await conn.execute(
                    "UPDATE user_commands SET command = 'continue_new' WHERE user_id = $1",
                    db_user_id
                )
                return {"status": "commad_new"}

            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_13", "✅ ")
            await conn.execute(
                "UPDATE user_commands SET command = 'new_dialogue' WHERE user_id = $1",
                db_user_id
            )
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_6", "🔥 ")
            return {"status": "commad_new"}

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////




        #/////////////////////////////////// ПРОДОВЖЕННЯ ОБРОБКИ ПЕРЕРИВАННЯ ДІАЛОГУ //////////////////////////////////////
        if command_value == 'continue_new':
            print(f"in body dialogue: {user_text}")
            
            row = await conn.fetchrow("SELECT language FROM users WHERE id = $1", db_user_id)
            if row:
                language = row["language"]
            else:
                language = 'eng'  # або значення за замовчуванням
            
            
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Determine whether the following phrase: {user_text} indicates agreement in the language specified by the ISO 639-2 code: {language}." 
                        f"Return the English word 'yes' if the phrase indicates agreement, or 'no' if it does not."
                        f"Return exactly yes or no as plain text, without any quotes or formatting."
                    )
                }
            ]
            user_answer = await query_openai_chat(messages)
            print(f"user_answer: {user_answer}")

            if user_answer.lower() in ("yes", "y"):
                # rezyumuvannya
                print(f"rezyumuvannya -----------------------------------")
                await summarize_dialogue(conn, dialogue_id, chat_id, db_user_id)
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_13", "✅ ")
            await conn.execute(
                "UPDATE user_commands SET command = 'new_dialogue' WHERE user_id = $1",
                db_user_id
            )
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_6", "🔥 ")
            return {"status": "commad_new"}
            
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        
        #/////////////////////// ОБРОБКА РЕСПОНСУ на питання НАЛАШТУВАНЬ СПІВРОЗМОВНИКА //////////////////////////////////////
        if command_value == 'new_dialogue':
            print(f"in body dialogue: {user_text}")
            
            row = await conn.fetchrow("SELECT language FROM users WHERE id = $1", db_user_id)
            if row:
                language = row["language"]
            else:
                language = 'eng'  # або значення за замовчуванням
            
            
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Determine whether the following phrase: {user_text} indicates agreement in the language specified by the ISO 639-2 code: {language}." 
                        f"Return the English word 'yes' if the phrase indicates agreement, or 'no' if it does not."
                        f"Return exactly yes or no as plain text, without any quotes or formatting."
                    )
                }
            ]
            
            # Отримуємо код країни
            user_answer = await query_openai_chat(messages)
            print(f"user_answer: {user_answer}")

            if user_answer.lower() in ("yes", "y"):
                #автоматчичне створення випадкового співрозмовника

        
                init_msg = await send_phrase(conn, bot, chat_id, db_user_id, "phrase_10", "✅ ")
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
                    await bot.send_message(chat_id=chat_id, text=f"❌ Parsing error: {e}")
                    return {"status": "error_parsing_profile"}

                # Вставляємо в базу
                # 1. Створюємо новий діалог і витягуємо його id
                dialogue_row = await conn.fetchrow(
                    """
                    INSERT INTO dialogues_stat (user_id) VALUES ($1)
                    RETURNING id
                    """,
                    db_user_id
                )
                dialogue_id = dialogue_row["id"]
                
                # 2. Вставляємо профіль з id_dialogue
                await conn.execute(
                    """
                    INSERT INTO simulated_personas (
                        user_id, name, age, country, difficulty_level, religious_context, personality,
                        barriers, openness, goal, big_five_traits, temperament, worldview_and_values,
                        beliefs, motivation_and_goals, background, erikson_stage, emotional_intelligence,
                        thinking_style, biological_factors, social_context, enneagram, disc_profile,
                        stress_tolerance, self_image, cognitive_biases, attachment_style, religion,
                        trauma_history, stress_level, habits, why_contacted_us, digital_behavior,
                        peer_pressure, attachment_history, culture, neuroprofile, meta_programs, philosophical_views,
                        id_dialogue
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, $17, $18,
                        $19, $20, $21, $22, $23,
                        $24, $25, $26, $27, $28,
                        $29, $30, $31, $32, $33,
                        $34, $35, $36, $37, $38, $39,
                        $40
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
                    dialogue_id  # ← додаємо сюди
                )
                
                await init_msg.delete()
                await send_phrase(conn, bot, chat_id, db_user_id, "phrase_8", "✅ ")   
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )
                    
                mark = 1
            else:
                await send_phrase(conn, bot, chat_id, db_user_id, "phrase_7", "✅ ")
                await conn.execute(
                    "UPDATE user_commands SET command = 'new_handle_dialogue' WHERE user_id = $1",
                    db_user_id
                )
                return {"status": "waiting_language"}




        
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #/////////////////////// ОБРОБКА РЕСПОНСУ на питання НАЛАШТУВАНЬ СПІВРОЗМОВНИКА //////////////////////////////////////
        if command_value == 'new_handle_dialogue':
            print(f"in body handle dialogue: {user_text}")

            #створення очикуваного співрозмовника
    
            init_msg = await send_phrase(conn, bot, chat_id, db_user_id, "phrase_10", "✅ ")

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
                await bot.send_message(chat_id=chat_id, text=f"❌ Parsing error: {e}")
                return {"status": "error_parsing_profile"}

            # Вставляємо в базу
            # 1. Створюємо новий діалог і витягуємо його id
            dialogue_row = await conn.fetchrow(
                """
                INSERT INTO dialogues_stat (user_id) VALUES ($1)
                RETURNING id
                """,
                db_user_id
            )
            dialogue_id = dialogue_row["id"]
            
            # 2. Вставляємо профіль з id_dialogue
            await conn.execute(
                """
                INSERT INTO simulated_personas (
                    user_id, name, age, country, difficulty_level, religious_context, personality,
                    barriers, openness, goal, big_five_traits, temperament, worldview_and_values,
                    beliefs, motivation_and_goals, background, erikson_stage, emotional_intelligence,
                    thinking_style, biological_factors, social_context, enneagram, disc_profile,
                    stress_tolerance, self_image, cognitive_biases, attachment_style, religion,
                    trauma_history, stress_level, habits, why_contacted_us, digital_behavior,
                    peer_pressure, attachment_history, culture, neuroprofile, meta_programs, philosophical_views,
                    id_dialogue
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7,
                    $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18,
                    $19, $20, $21, $22, $23,
                    $24, $25, $26, $27, $28,
                    $29, $30, $31, $32, $33,
                    $34, $35, $36, $37, $38, $39,
                    $40
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
                dialogue_id  # ← додаємо сюди
            )
            
            await init_msg.delete()
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_8", "✅ ")   
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
        print(f"row ----------------------------------------- : {row}")
        
        if row:
            print("✅ Користувач існує і поле phrase_1 заповнене")
            row_1 = await conn.fetchrow(
                "SELECT phrase_1 FROM translated_phrases WHERE user_id = $1",
                db_user_id
            )
            
            if row_1 is not None:
                phrase_value = row_1['phrase_1']  # Отримуємо значення phrase_1
                print(f"Значення phrase_1: {phrase_value}")

        else:
            print(f"Зберігаємо переклад службових реплік")
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
                "Initializing the characteristics of your conversation partner...", # - phrase_10
                "The profile of your conversation partner already exists. Let's continue the dialogue.", # - phrase_11
                "Your dialogue has come to an end. We will now conduct a detailed analysis and summarize the results.", # - phrase_12
                "\n\nThank you for the conversation. \nYou will automatically be offered to generate a new respondent profile and start a new dialogue.", # - phrase_13
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
    

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        #/////////////////////////////////////// ТЕСТ комірки ДЕ ВКАЗАНО ІМЯ ////////////////////////////////////////////////
        if not existing_user["name"]:
            print(f"Тест пустої комірки імя")


            await conn.execute("""
                INSERT INTO user_commands (user_id, command)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
            """, db_user_id, "name")



            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_1", "🔥 ")
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



            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_4", "🔥 ")
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



            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_6", "🔥 ")
            await conn.execute(
                "UPDATE users SET initial = $1 WHERE id = $2",
                'pss', db_user_id
            )
            return {"status": "waiting_seeker_status"}

        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
        
        #///////////////////////////////// ПИТАННЯ чи ОСТАННЯ ДІЯ БУЛА ОБРОБНИКОМ таблиці users /////////////////////////////
        if mark == 1:
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_9", "🔥 ")
            return {"status": "data_updated"}
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



        
        #====================================================================================================================
        #////////////////////////////////////////////////////// ДІАЛОГ  //////////////////////////////////////////////////////
        #====================================================================================================================

        
        thinking_msg = await bot.send_message(chat_id=chat_id, text="🧠 Думаю...")


        msg_count, dialogue_id = await increment_message_count(conn, db_user_id)
        print("📦 dialogue_id:", dialogue_id)

        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at, id_dialogue) VALUES ($1, 'user', $2, NOW(), $3)",
            db_user_id, user_text, dialogue_id
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

        print("📦 user_id:", db_user_id)
        # Витягнути профіль із бази для користувача (припустимо, user_id)
        profile_row = await conn.fetchrow(
            "SELECT * FROM simulated_personas WHERE user_id = $1 AND id_dialogue = $2",
            db_user_id, dialogue_id
        )
        #print("📦 profile_row:", profile_row)
        if not profile_row:
            # Якщо профілю немає, можеш повернути порожній список або дефолтний профіль
            print("📦 profile is empty:")
            profile_content = "{}"
        else:
            # Припустимо, що профіль у таблиці збережений у полі profile_json у вигляді JSON рядка
            # Збираємо словник із профілем
            profile_content = {
                "name": profile_row["name"],
                "age": profile_row["age"],
                "country": profile_row["country"],
                "difficulty_level": profile_row["difficulty_level"],
                "religious_context": profile_row["religious_context"],
                "personality": profile_row["personality"],
                "barriers": profile_row["barriers"],  # якщо список — залишаємо
                "openness": profile_row["openness"],
                "goal": profile_row["goal"],
                "big_five_traits": json.loads(profile_row["big_five_traits"]),
                "temperament": profile_row["temperament"],
                "worldview_and_values": profile_row["worldview_and_values"],
                "beliefs": profile_row["beliefs"],
                "motivation_and_goals": profile_row["motivation_and_goals"],
                "background": profile_row["background"],
                "erikson_stage": profile_row["erikson_stage"],
                "emotional_intelligence": profile_row["emotional_intelligence"],
                "thinking_style": profile_row["thinking_style"],
                "biological_factors": profile_row["biological_factors"],
                "social_context": profile_row["social_context"],
                "enneagram": profile_row["enneagram"],
                "disc_profile": profile_row["disc_profile"],
                "stress_tolerance": profile_row["stress_tolerance"],
                "self_image": profile_row["self_image"],
                "cognitive_biases": profile_row["cognitive_biases"],
                "attachment_style": profile_row["attachment_style"],
                "religion": profile_row["religion"],
                "trauma_history": profile_row["trauma_history"],
                "stress_level": profile_row["stress_level"],
                "habits": profile_row["habits"],
                "why_contacted_us": profile_row["why_contacted_us"],
                "digital_behavior": profile_row["digital_behavior"],
                "peer_pressure": profile_row["peer_pressure"],
                "attachment_history": profile_row["attachment_history"],
                "culture": profile_row["culture"],
                "neuroprofile": profile_row["neuroprofile"],
                "meta_programs": profile_row["meta_programs"],
                "philosophical_views": profile_row["philosophical_views"],
            }
        
            # перетворимо на гарно форматований текст
            profile_content = json.dumps(profile_content, ensure_ascii=False, indent=2)
            #print("📦 profile_content:", profile_content)
        
        # Створюємо system prompt
        system_message = {
            "role": "system",
            "content": f"You behave like a person who possesses the personality traits specified in the profile: {profile_content}. You do not take the initiative to offer consultative help as a typical chat assistant would. Instead, you tend to ask simple or banal questions yourself."
        }
        
        # Далі формуємо список повідомлень, додаємо system_message спочатку, потім user_messages
        messages = [system_message] + user_messages

    
        # messages = [{"role": row["role"], "content": row["message"]} for row in rows]
        # messages = [{'role': 'user', 'content': user_text}]

        response_text = await query_openai_chat(messages)

  
        await conn.execute(
            "INSERT INTO dialogs (user_id, role, message, created_at, id_dialogue) VALUES ($1, 'ai', $2, NOW(), $3)",
            db_user_id, response_text, dialogue_id
        )
        
        try:
            await thinking_msg.delete()
        except:
            pass

        await bot.send_message(chat_id=chat_id, text=response_text)

        #====================================================================================================================
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
        #====================================================================================================================

        

        #///////////////////////////////// ПИТАННЯ ЗАВЕРШЕННЯ ДІАЛОЛГУ (вичерпання месиджів) ////////////////////////////////
        if msg_count and msg_count >= 11:
            init_msg = await bot.send_message(chat_id=chat_id, text=f"🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔")
            await asyncio.sleep(5)  # Затримка 5 секунд
            await init_msg.delete()
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_12", "✅ ")
            await summarize_dialogue(conn, dialogue_id, chat_id, db_user_id)
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_13", "✅ ")
            await conn.execute(
                "UPDATE user_commands SET command = 'new_dialogue' WHERE user_id = $1",
                db_user_id
            )
            await send_phrase(conn, bot, chat_id, db_user_id, "phrase_6", "🔥 ")
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
           


    




    finally:
        await conn.close()


    return {"status": "ok"}
