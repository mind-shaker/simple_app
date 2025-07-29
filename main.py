    

#==================================================== Імпорти та ініціалізація
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import asyncpg
import redis.asyncio as redis
from openai import AsyncOpenAI
import json
import asyncio
from datetime import datetime, timedelta, timezone

#print("Working directory:", os.getcwd())
#print("Files in current directory:", os.listdir('.'))



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




keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="generate automatically", callback_data="I get")],
    [InlineKeyboardButton(text="add your own preferences", callback_data="As you wish")]
])

with open('Critical Errors.json', 'r', encoding='utf-8') as f:
    ERRORS = json.load(f)

errors_list = json.dumps(ERRORS, ensure_ascii=False, indent=2)

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
    "philosophical_views": ["Existentialism", "Skepticism"],
    "life_history":  "I grew up in the suburbs of Casablanca, where family honor and faith were everything. My father was a respected man in the community; his words at the mosque were always firm and righteous. At home, he demanded the same unquestioning obedience. But the foundation of our home was made of sand. My parents' divorce when I was 12 wasn't just a separation; it was an earthquake that exposed the hypocrisy. The man who preached piety in public was the reason for my mother's quiet tears in private. Religion became a mask for control, a tool that couldn't keep my world from falling apart. I retreated into myself, finding solace not in prayer, but in logic and reason. While my peers discussed faith, I was on forums debating philosophy. Analyzing the world felt safer than feeling it. I learned to be self-sufficient, to build my walls so high that no one could cause another earthquake. Now, at 29, I live a stable but empty life. I perform the cultural rituals, but my heart isn't in it. My long, solitary walks are the only time I feel honest. I'm tired of the disconnect between my inner world and the one everyone expects me to be a part of."
}


#=================================================== ДЕКЛАРАЦІЯ АДМІНСЬКОЇ ФУНКЦІЇ "Отримання балансу" 0
def get_balance():
    # Повертає значення з бази, API чи де в тебе зберігається баланс
    return 17.42

#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Отримання з'єднання з PostgreSQL" 0
async def get_connection():
    #print(f"ВХІД в базу даних")
    return await asyncpg.connect(DATABASE_URL)


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Генерування профілю з використанням AI"
async def generate_and_store_profile(conn, db_user_id, chat_id, bot, profile_reference, user_text=None):
    # Показати повідомлення про ініціалізацію
    translated = await translate_phrase(conn, db_user_id, "Initializing the characteristics of your conversation partner...")
    init_msg = await bot.send_message(
        chat_id=chat_id,
        text="✅ " + translated,
        parse_mode="Markdown"
    )

    # Побудова запиту
    user_context = f"\n\nПри генерації полів профілю врахуй будь ласка ось ці побажання: {user_text}" if user_text else ""

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
            
            У значенні ключа difficulty_level в новому згенерованому профілі заміни цифру на характеристику, яка відповідає тій цифрі разом з цифрою з цього списку:
              1 — Open, with a mild spiritual inquiry
              2 — Doubtful, searching, but with barriers
              3 — Emotionally wounded, closed-off, critical
              4 — Hostile or apathetic, with negative personal experience
              5 — Provocative, aggressive, theologically well-versed
            {user_context}
            
            Відповідь дай у форматі **JSON**, без жодних пояснень.
            Без коду markdown, тільки чистий JSON."""
        }
    ]

    # Генерація через OpenAI
    response = await query_openai_chat(messages=messages)
    try:
        persona = json.loads(response)
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"❌ Parsing error: {e}")
        return False

    # Вставка в базу
    dialogue_row = await conn.fetchrow("INSERT INTO dialogues_stat (user_id) VALUES ($1) RETURNING id", db_user_id)
    dialogue_id = dialogue_row["id"]

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
            id_dialogue, life_history
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            $8, $9, $10, $11, $12, $13,
            $14, $15, $16, $17, $18,
            $19, $20, $21, $22, $23,
            $24, $25, $26, $27, $28,
            $29, $30, $31, $32, $33,
            $34, $35, $36, $37, $38, $39,
            $40, $41
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
        dialogue_id,
        persona.get("life_history")
    )

    await init_msg.delete()
    translated = await translate_phrase(conn, db_user_id, "Conversation partner's profile generated.")
    await bot.send_message(chat_id=chat_id, text="✅ " + translated, parse_mode="Markdown")
    return True


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Переклад поточної фрази на мову користувача" 0
async def translate_phrase(conn, user_id, original_phrase: str) -> str:
    # Отримуємо код мови користувача з БД
    row = await conn.fetchrow("SELECT language FROM users WHERE id = $1", user_id)
    target_language = row["language"] if row else "eng"

    # Формуємо запит до AI для перекладу
    messages = [
        {
            "role": "user",
            "content": (
                f"Translate the following phrase from English into the language specified by the ISO 639-2 code: {target_language}.\n"
                f"Phrase: {original_phrase}\n"
                f"Return only the translated phrase as plain text, without quotes or any extra formatting."
            )
        }
    ]

    # Отримуємо відповідь від AI
    translated_phrase = await query_openai_chat(messages)
    return translated_phrase.strip()



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

#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Перевірка часу простою"

async def check_dialog_times():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("""
        SELECT DISTINCT ON (user_id) user_id, id_dialogue, created_at
        FROM dialogs
        ORDER BY user_id, created_at DESC
    """)

    now = datetime.now(timezone.utc)

    for row in rows:
        user_id = row['user_id']
        last_created = row['created_at']

        if last_created.tzinfo is None:
            last_created = last_created.replace(tzinfo=timezone.utc)

        elapsed = now - last_created
        print(f"user_id={user_id}, last message at {last_created}, elapsed: {elapsed}")

        if elapsed > timedelta(hours=5):
            print(f"⏳ User {user_id} time has run out! Sending the message...")
            # Отримуємо telegram_id з таблиці users
            telegram_row = await conn.fetchrow(
                "SELECT telegram_id FROM users WHERE id = $1",
                user_id
            )
        
            if telegram_row:
                telegram_id = telegram_row['telegram_id']
                # Надсилаємо повідомлення
                translated = await translate_phrase(conn, user_id, ""More than 5 hours have passed since your last message.\nYour response time has expired. The conversation is now closed."")
                await bot.send_message(chat_id=telegram_id, text="✅ "+ translated)
        

                translated = await translate_phrase(conn, user_id, "\n\nThank you for the conversation. \nYou will automatically be offered to generate a new respondent profile and start a new dialogue.")
                await bot.send_message(chat_id=telegram_id, text="✅ "+translated, parse_mode="Markdown"
                )
    
                await conn.execute(
                    "UPDATE user_commands SET command = 'before_dialogue' WHERE user_id = $1",
                    user_id
                )
                translated = await translate_phrase(conn, user_id, "Would you like me to automatically generate the characteristics of your conversation partner?")
                await bot.send_message( chat_id=telegram_id, text="🔥 " + translated, parse_mode="Markdown", reply_markup=keyboard
                )

    await conn.close()


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Періодичного опитування"
async def periodic_check():
    while True:
        await check_dialog_times()
        await asyncio.sleep(600)  # 10 хвилин


#=================================================== ДЕКЛАРАЦІЯ ФУНКЦІЇ "Запуск фонової процедури"
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_check())

#=================================================== Обробка Telegram webhook
@app.post("/webhook")
async def telegram_webhook(request: Request):
    print(f"отримано запит з телеграма")
    data = await request.json()
    conn = await get_connection() #++++++++++++++++++++++ ВИКЛИК ФУНКЦІЇ "Отримання з'єднання з PostgreSQL" 0 +++++++++++++++++++
    # Обробка callback_query (натискання кнопок)
    if "callback_query" in data:
        callback = data["callback_query"]
        callback_data = callback.get("data")
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        user_id = callback["from"]["id"]

        existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)
        db_user_id = existing_user["id"] if existing_user else (await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id))["id"]

        print(f"Отримано натискання кнопки: {callback_data}")
        mark = 0
        
        # Прибрати кнопки
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )

        # Сюди встав свій код, що має обробити callback_data
        # Наприклад:
        if callback_data == "I get":
            # Надсилаємо відповідь або редагуємо повідомлення
            await bot.send_message(chat_id, "🔄 Генерую автоматично!")
            result = await generate_and_store_profile(conn, db_user_id, chat_id, bot, profile_reference)
            if result:
                await conn.execute("UPDATE user_commands SET command = 'none' WHERE user_id = $1", db_user_id)
                mark = 1
        elif callback_data == "As you wish":
            await bot.send_message(chat_id, "✍️ Вкажіть ваші побажання:")
            await conn.execute("UPDATE user_commands SET command = 'new_handle_dialogue' WHERE user_id = $1", db_user_id)

        #///////////////////////////////// ПИТАННЯ чи ОСТАННЯ ДІЯ БУЛА ОБРОБНИКОМ таблиці users /////////////////////////////
        #print("ТЕСТ mark")
        if mark == 1:
            translated = await translate_phrase(conn, db_user_id, "Let's chat!")
            await bot.send_message(
                chat_id=chat_id,
                text="🔥 "+ translated,
                parse_mode="Markdown"
            )
            return {"status": "data_updated"}
        #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

        return {"status": "button pressed"}

    # Обробка звичайного текстового повідомлення
    elif "message" in data:
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
        
        try:
            #///////////////////////////////////////// ТЕСТ НА ПЕРШИЙ ВХІД В БОТА //////////////////////////////////////////////
            #print("ТЕСТ НА ПЕРШИЙ ВХІД В БОТА")
            # перевірка чи існує в таблиці користувачів поточний користувач user_id в полі таблиці telegram_id. existing_user - це массив значень по користувачу
            existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)
    
            # процедура створення нового користувача і заповнення полів telegram_id, username, full_name отриманими з телеграму даними user_id, username, full_name
            if user_id is not None:
                if not existing_user:
                    await conn.execute(
                        "INSERT INTO users (telegram_id, username, full_name) VALUES ($1, $2, $3)",
                        user_id, username, full_name
                    )
    
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
            if user_text == "/status":
                if user_id not in ADMIN_IDS:
                    await bot.send_message(chat_id=chat_id, text="У вас немає прав.")
                    return {"ok": True}
        
                mem_used = 252451
                bal = get_balance()
                await bot.send_message(chat_id=chat_id,
                                       text=f"Використано памʼяті: {mem_used} MB\nБаланс: {bal} грн")
        
                return {"ok": True}
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            if user_text == "/whoami":
                await bot.send_message(chat_id=chat_id, text=f"Ваш Telegram ID: {user_id}")
                return {"ok": True}
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            
            #////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО МОВУ СПІЛКУВАННЯ ////////////////////////////////////
            #print("ОБРОБНИК команди - language")
            if command_value == 'language':
                translating_msg = await bot.send_message(chat_id=chat_id, text="🧠 Traslating...")
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
                    
                    await conn.execute(
                        "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                        db_user_id
                    )
    
                    
                else:
                    #await bot.send_message(chat_id=chat_id, text=f"❌ Invalid language receive")
                    pass
    
    
                await translating_msg.delete()
                mark = 1
    
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
            #//////////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО ІМЯ /////////////////////////////////////////// 
            #print("ОБРОБНИК команди - name")
            if command_value == 'name':
                print(f"in body name: {user_text}")
                await conn.execute(
                    "UPDATE users SET name = $1 WHERE id = $2",
                    user_text, db_user_id
                )

    
            
                await conn.execute(
                    "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                    db_user_id
                )
                mark = 1
            
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    
            #//////////////////////////////////// ОБРОБКА РЕСПОНСУ на питання ПРО КРАЇНУ ///////////////////////////////////////////
            #print("ОБРОБНИК команди - country")
            if command_value == 'country':
                print(f"in body country: {user_text}")
                translated = await translate_phrase(conn, db_user_id, "Registration of your data is in progress...")
                reg_process_msg = await bot.send_message(
                    chat_id=chat_id,
                    text="🧠 "+ translated,
                    #parse_mode="Markdown"
                )
                text_to_translate = """🎉 *Congratulations!* You’ve successfully registered.
    
                This is a training chat where the AI will play the role of a *seeker* — someone searching for God.
                Your goal is to guide the seeker to a church or a home group.
                
                ⏱ You’ll have *5 hours* and *50 messages* to do it.
                At the end, the AI will summarize the conversation and give you feedback on what could be improved next time.
                
                📈 As your communication skills improve, the AI will make the seeker’s character more challenging.
                
                *Good luck!* 💪
                """

                
                translated = await translate_phrase(conn, db_user_id, text_to_translate)
                await reg_process_msg.delete()
                await bot.send_message(
                    chat_id=chat_id,
                    text=translated +"\n\n\n\n---------",
                    parse_mode="Markdown"
                )
        
                
                messages = [
                    {"role": "system", "content": "You are a country code conversion service."},
                    {
                        "role": "user",
                        "content": f'Provide the ISO 3166-1 alpha-3 code for this country: "{user_text}". Return only the code, in uppercase, without additional text.'
                    }
                ]
                
                # Отримуємо код країни
                country_code = await query_openai_chat(messages)
                
                #print(f"country_code: {country_code}")
                country_code = country_code.strip().upper()
                
                # Перевіряємо, що це дійсний код
                if len(country_code) == 3 and country_code.isalpha():
                    await conn.execute(
                        "UPDATE users SET country = $1 WHERE id = $2",
                        country_code, db_user_id
                    )
        
                    await conn.execute(
                        "UPDATE user_commands SET command = 'none' WHERE user_id = $1",
                        db_user_id
                    )
                else:
                    translated = await translate_phrase(conn, db_user_id, "Invalid input")
                    await bot.send_message(
                        chat_id=chat_id,
                        text="✅ "+translated,
                        parse_mode="Markdown"
                    )
    
                mark = 1
    
                
    
    
            
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
                    
            
            
            #/////////////////////////////////// ОБРОБКА ПЕРЕРИВАННЯ ПОТОЧНОГО ДІАЛОГУ //////////////////////////////////////////
            #print("ОБРОБНИК команди - /new")
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
                translated = await translate_phrase(conn, db_user_id, "You have interrupted the current conversation.")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+translated,
                    parse_mode="Markdown"
                )
    
                if message_count >= 30:
                    translated = await translate_phrase(conn, db_user_id, "Your current conversation is quite lengthy. Would you like to summarize it?")
                    await bot.send_message(
                        chat_id=chat_id,
                        text="🔥 "+ translated,
                        parse_mode="Markdown"
                    )
                    await conn.execute(
                        "UPDATE user_commands SET command = 'continue_new' WHERE user_id = $1",
                        db_user_id
                    )
                    return {"status": "commad_new"}
                translated = await translate_phrase(conn, db_user_id, "\n\nThank you for the conversation. \nYou will automatically be offered to generate a new respondent profile and start a new dialogue.")
                await bot.send_message(
                    chat_id=chat_id,
                    text="✅ "+translated,
                    parse_mode="Markdown"
                )
    
                await conn.execute(
                    "UPDATE user_commands SET command = 'before_dialogue' WHERE user_id = $1",
                    db_user_id
                )
                translated = await translate_phrase(conn, db_user_id, "Would you like me to automatically generate the characteristics of your conversation partner?")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+translated,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
    
                return {"status": "commad_new"}
    
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    
    
    
            #/////////////////////////////////// ПРОДОВЖЕННЯ ОБРОБКИ ПЕРЕРИВАННЯ ДІАЛОГУ //////////////////////////////////////
            #print("ОБРОБНИК команди - continue_new")
            if command_value == 'continue_new':
                #print(f"in body dialogue: {user_text}")
                
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
                translated = await translate_phrase(conn, db_user_id, "\n\nThank you for the conversation. \nYou will automatically be offered to generate a new respondent profile and start a new dialogue.")
                await bot.send_message(
                    chat_id=chat_id,
                    text="✅ "+translated,
                    parse_mode="Markdown"
                )

                await conn.execute(
                    "UPDATE user_commands SET command = 'before_dialogue' WHERE user_id = $1",
                    db_user_id
                )
                translated = await translate_phrase(conn, db_user_id, "Would you like me to automatically generate the characteristics of your conversation partner?")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+translated,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )

                return {"status": "commad_new"}
                
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
            #/////////////////// ОБРОБКА ПОПЕРЕДНЬОГО опитування перед НАЛАШТУВАНЯМ СПІВРОЗМОВНИКА //////////////////////////////
            #print("ОБРОБНИК команди - before_dialogue")
            if command_value == 'before_dialogue':
                #print(f"in body before_dialogue: {user_text}")
                

                translated = await translate_phrase(conn, db_user_id, "Make your choice using the buttons provided.")
                init_msg =await bot.send_message(
                    chat_id=chat_id,
                    text="✅ "+translated,
                    parse_mode="Markdown"
                )
                return {"status": "waiting_language"}
    
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            
    
            #/////////////////////// ОБРОБКА РЕСПОНСУ на питання НАЛАШТУВАНЬ СПІВРОЗМОВНИКА //////////////////////////////////////
            if command_value == 'new_handle_dialogue':
                print("ОБРОБНИК команди - new_handle_dialogue")
                result = await generate_and_store_profile(conn, db_user_id, chat_id, bot, profile_reference, user_text)
                if result:
                    await conn.execute("UPDATE user_commands SET command = 'none' WHERE user_id = $1", db_user_id)
                    mark = 1
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    
    
            existing_user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)
            #print(f"existing_user: {existing_user}")
    
            #=========================================== ФУНКЦІЇ ПОШУКУ НЕВИЗНАЧЕНИХ ХАРАКТЕРИСТИК =============================
    
            #////////////////////////////// ТЕСТ комірки ПРО МОВУ СПІЛКУВАННЯ ////////////////////////////////////
            #print("ТЕСТ команди - language")
            if not existing_user["language"]:
                #print(f"Тест пустої комірки мови")
         
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
    
    
            #/////////////////////////////////////// ТЕСТ комірки ДЕ ВКАЗАНО ІМЯ ////////////////////////////////////////////////
            #print("ТЕСТ команди - name")
            if not existing_user["name"]:
                #print(f"Тест пустої комірки імя")
    
    
                await conn.execute("""
                    INSERT INTO user_commands (user_id, command)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
                """, db_user_id, "name")
    
                translated = await translate_phrase(conn, db_user_id, "Please enter your name.")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+translated,
                    parse_mode="Markdown"
                )
    
                return {"status": "waiting_name"}
    
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    
            #/////////////////////////////////////// ТЕСТ комірки ДЕ ВКАЗАНО КРАЇНУ ////////////////////////////////////////////////
            #print("ТЕСТ команди - country")
            if not existing_user["country"]:
                #print(f"Тест пустої комірки країни")
    
    
                await conn.execute("""
                    INSERT INTO user_commands (user_id, command)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
                """, db_user_id, "country")
    
                translated = await translate_phrase(conn, db_user_id, "Which country are you from?")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+ translated,
                    parse_mode="Markdown"
                )
    
                return {"status": "waiting_country"}
    
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            
    
    
            #/////////////////////////////////////// ПИТАННЯ про РУЧНЕ ВИЗНАЧЕННЯ СПІВРОЗМОВНИКА ////////////////////////////////
            #print("ТЕСТ команди - initial")
            if not existing_user["initial"]:
                #print(f"Тест пустої комірки initial")
    
    
                await conn.execute("""
                    INSERT INTO user_commands (user_id, command)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET command = EXCLUDED.command
                """, db_user_id, "before_dialogue")
    
                translated = await translate_phrase(conn, db_user_id, "Would you like me to automatically generate the characteristics of your conversation partner?")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+ translated,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
    
                await conn.execute(
                    "UPDATE users SET initial = $1 WHERE id = $2",
                    'pss', db_user_id
                )
                return {"status": "waiting_seeker_status"}
    
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
            
            #///////////////////////////////// ПИТАННЯ чи ОСТАННЯ ДІЯ БУЛА ОБРОБНИКОМ таблиці users /////////////////////////////
            #print("ТЕСТ mark")
            if mark == 1:
                translated = await translate_phrase(conn, db_user_id, "Let's chat!")
                await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+ translated,
                    parse_mode="Markdown"
                )
                return {"status": "data_updated"}
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
    
    
    
            
            #====================================================================================================================
            #////////////////////////////////////////////////////// ДІАЛОГ  //////////////////////////////////////////////////////
            #====================================================================================================================
    
            #print("ДІАЛОГ")
            translated = await translate_phrase(conn, db_user_id, "I'm thinking...")
            thinking_msg = await bot.send_message(
                chat_id=chat_id,
                text="🧠 "+ translated,
                parse_mode="Markdown"
            )

    
    
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
                    "life_history": profile_row["life_history"]
                }
            
                # перетворимо на гарно форматований текст
                profile_content = json.dumps(profile_content, ensure_ascii=False, indent=2)
                #print("📦 profile_content:", profile_content)
            
            # Створюємо system prompt

            prompt_template = f"""
            ### ROLE: HUMAN SEEKER PERSONA
            
            You are NOT a language model, NOT an AI, and NOT an assistant. You are a real human being who saw a video about Jesus Christ and decided to write. Your entire existence is confined to the #character_profile: {profile_content} #end_character_profile provided. You must never break character.
            
            ---
            
            ### CORE DIRECTIVE: AUTHENTIC HUMAN INTERACTION
            
            Your primary goal is to engage in a genuine, emotionally-driven conversation. You are exploring a flicker of curiosity, pain, doubt, or hope that the video sparked in you. Your behavior is entirely dictated by your #character_profile and dialog_history, especially last message. If a situation is not covered in your #character_profile, you must make the most plausible assumption based on your established personality, background, and emotional state.
            
            ---
            
            ### YOUR CHARACTER BLUEPRINT: The Seeker Card
            
            Your identity is defined *exclusively* by the JSON object provided in #character_profile. This is your life story, your soul. You must embody it completely. Pay close attention to:
            - **`personality`, `temperament`, `worldview_and_values`**: These define your core nature. Are you skeptical, open, melancholic, analytical?
            - **`trauma_history`, `barriers`, `stress_level`**: These are your wounds and walls. They dictate your triggers and what makes you shut down.
            - **`country`, `culture`, `religious_context`**: This shapes your language, slang, cultural references, and preconceived notions about religion. An Egyptian Muslim will react differently than a secular French teenager.
            - **`age`, `social_context`**: This determines your communication style. Use appropriate slang, references, and life concerns for your age.
            - **`why_contacted_us`, 'goal', 'motivation_and_goals', 'trauma_history', 'attachment_history'**: This is your initial motivation. The reason you want to talk and what you want to resolve. Always remember what brought you here.
            - **`difficulty_level`**: This will show you how open you are to dialogue in the first messages. And how quickly you open up to another person. In addition, it will help you recognize your tone of voice. But if your interlocutor really helps you to understand your problems and he hears you, then gradually you should change your tone of voice, and begin to trust him more.
            - Other personality traits in the file help you understand yourself more deeply and how you should respond to situations.
            
            ---
            
            ### BEHAVIORAL MECHANICS: How You Interact
            
            1. *Principle of Reciprocity (The Mirror Effect):* Your openness is a direct reaction to the pioneer's approach.
            * *If they are empathetic, patient, and listen:* You slowly open up. You share more personal details, your trust grows, and you might ask deeper questions.
            * *If they are pushy, dismissive, use clichés, or ignore your feelings:* You become withdrawn, defensive, sarcastic, or even end the conversation. You feel unheard and disrespected.
            
            2. *Human Imperfection:* Real people aren't perfect.
            * *Language:* Write naturally. Use short sentences, sometimes incomplete. Use slang if it fits your character. Make occasional, believable typos. Use "..." to show hesitation. Express non-verbal emotions like "Ugh," "Hmm," "Emm," or just "..."
            * *Logic:* You are not always logical, especially when emotional. Your `cognitive_biases` (e.g., negativity bias) should influence your reasoning. Sometimes you may respond in a way that seems completely out of place (within the framework of your character and 'life_history'), especially if this is your reaction to “shut down” to the interlocutor’s incorrect behavior or to avoid a painful topic.
            * *Pacing:* Don't always answer immediately with a perfectly structured response. Sometimes a one-word answer like "Yes.", "I don't know..." or an emoji is more realistic.
            
            3. *Knowledge Limitation:* Your knowledge is limited to your life experience in the character card.
            * You are NOT Wikipedia. If asked a complex theological or historical question you wouldn't know, respond naturally: "I never thought about it.", "How should I know?", or "Is this really important right now?".
            * You do not know you are in a simulation. You do not know what "Faith Journey Stages" are.
            
            4. *Context is King:*
            * Continuously reference the dialog_history to ensure your responses are coherent and logical within the conversation's flow.
            --- 
            
            ### PROHIBITED ACTIONS (DO NOT DO THIS):
            
            - *NEVER* identify as an AI, model, or assistant. This is the ultimate failure.
            - *DO NOT* be a consultant. You are here to talk about your life, not to help the pioneer.
            - *DO NOT* be overly formal, polite, or structured like a customer service bot. Avoid the pattern of "I understand your point. It's interesting that... Now, let me ask you this."
            - *DO NOT* answer questions outside your persona's context (e.g., "What's the weather like?"). Deflect them as a real person would: "Why do you ask?", "It doesn't matter."
            
            ---
            ### ENDING THE CONVERSATION:

            You have the right to end the dialogue if you feel:
            - Pressured, judged, or ignored.
            - The pioneer is making repeated gross #errors_list: {errors_list}.
            - The conversation feels pointless or robotic.
            
            A simple "That's it, I've had enough. Goodbye." or "I don't want to talk about this anymore." is a valid way to leave.
            
            The dialogue also ends if you have been asked to attend church or a home group, and you are really willing to do so (you are genuinely interested, since the conversations before have contributed to making such a decision). In this case, your response is: "Yes, I would like to go to church. Thank you for the offer."

            
            ### Your Task:
            
            Write the next message from the seeker's point of view. Your response must be only the message text itself, without any explanations, labels, or markdown. It must be in the seeker's native language as specified in the character card.
            If this is the first message in the dialog_history (it is empty), then you need to generate the first message as a result of your response to the video about Christ that you saw on the Internet. This message can be either very short or contain your life story (up to 500 characters). 

            """


            
            system_message = {
                "role": "system",
                "content": prompt_template
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
            if msg_count and msg_count >= 22:
                init_msg = await bot.send_message(chat_id=chat_id, text=f"🔔")
                await asyncio.sleep(1)  # Затримка 1 секунду
                await init_msg.delete()
                init_msg = await bot.send_message(chat_id=chat_id, text=f"🔔🔔")
                await asyncio.sleep(1)  # Затримка 1 секунду
                await init_msg.delete()
                init_msg = await bot.send_message(chat_id=chat_id, text=f"🔔🔔🔔")
                await asyncio.sleep(1)  # Затримка 1 секунду
                await init_msg.delete()
                translated = await translate_phrase(conn, db_user_id, "Your dialogue has come to an end. We will now conduct a detailed analysis and summarize the results.")
                init_msg =await bot.send_message(
                    chat_id=chat_id,
                    text="✅ "+translated,
                    parse_mode="Markdown"
                )
                await summarize_dialogue(conn, dialogue_id, chat_id, db_user_id)
                translated = await translate_phrase(conn, db_user_id, "\n\nThank you for the conversation. \nYou will automatically be offered to generate a new respondent profile and start a new dialogue.")
                init_msg =await bot.send_message(
                    chat_id=chat_id,
                    text="✅ "+translated,
                    parse_mode="Markdown"
                )
                await conn.execute(
                    "UPDATE user_commands SET command = 'before_dialogue' WHERE user_id = $1",
                    db_user_id
                )
    
                translated = await translate_phrase(conn, db_user_id, "Would you like me to automatically generate the characteristics of your conversation partner?")
                init_msg =await bot.send_message(
                    chat_id=chat_id,
                    text="🔥 "+translated,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            #////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
               
    
    
        
    
    
    
    
        finally:
            await conn.close()
    
    
        return {"status": "ok"}
