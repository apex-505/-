import asyncio
import logging
import sys
import os
import random
import time
sqlite3 = __import__('sqlite3')
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = "8844473296:AAHZ0qrpucOehAFnNFNWNSvnZ5ae9emJewA"

dp = Dispatcher()

# Инициализация базы данных SQLite (добавили колонку last_time для кулдауна)
def init_db():
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendship (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER,
            last_time REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я твой админ-бот. Напиши <b>.почесать</b> (можно раз в 4 часа), чтобы заработать баллы дружбы, или <b>.баланс</b>, чтобы проверить свой счет!"
    )

# Команда .почесать (или /pochesat) с кулдауном 4 часа
@dp.message(F.text.lower().in_({".почесать", "/pochesat"}))
async def cmd_pochesat(message: Message):
    user = message.from_user
    current_time = time.time()
    cooldown = 4 * 60 * 60  # 4 часа в секундах
    
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    
    # Проверяем запись о пользователе
    cursor.execute('SELECT points, last_time FROM friendship WHERE user_id = ?', (user.id,))
    row = cursor.fetchone()
    
    if row is not None:
        points, last_time = row
        time_diff = current_time - last_time
        if time_diff < cooldown:
            # Если прошло меньше 4 часов, считаем оставшееся время
            timeLeft = int(cooldown - time_diff)
            hours = timeLeft // 3600
            minutes = (timeLeft % 3600) // 60
            conn.close()
            await message.answer(
                f"⏳ @{user.username or user.first_name}, ты уже чесал карму недавно! "
                f"Следующий раз будет доступен через <b>{hours} ч. {minutes} мин.</b>"
            )
            return
    
    # Если кулдаун прошел или пользователь пишет впервые
    earned_points = random.randint(1, 10)  # баллы от 1 до 10
    
    if row is None:
        total_points = earned_points
        cursor.execute(
            'INSERT INTO friendship (user_id, username, points, last_time) VALUES (?, ?, ?, ?)', 
            (user.id, user.username or user.first_name, total_points, current_time)
        )
    else:
        total_points = row[0] + earned_points
        cursor.execute(
            'UPDATE friendship SET points = ?, last_time = ? WHERE user_id = ?', 
            (total_points, current_time, user.id)
        )
        
    conn.commit()
    conn.close()
    
    await message.answer(
        f"🤗 @{user.username or user.first_name} почесал за ушком свою карму и получил <b>+{earned_points}</b> балл(ов) дружбы!\n"
        f"📊 Всего баллов: <b>{total_points}</b>"
    )

# Команда .баланс (или /balans)
@dp.message(F.text.lower().in_({".баланс", "/balans"}))
async def cmd_balans(message: Message):
    user = message.from_user
    
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('SELECT points FROM friendship WHERE user_id = ?', (user.id,))
    row = cursor.fetchone()
    conn.close()
    
    points = row[0] if row else 0
    await message.answer(
        f"📊 У тебя на счету <b>{points}</b> балл(ов) дружбы."
    )

@dp.message(Command("mute"))
async def cmd_mute(message: Message):
    if not message.reply_to_message:
        await message.answer(
            "Эту команду нужно вызывать ответом на сообщение нарушителя!"
        )
        return
    target_user = message.reply_to_message.from_user
    admin = message.from_user
    await message.answer(
        f"🔇 Администратор @{admin.username or admin.first_name} замутил "
        f"пользователя @{target_user.username or target_user.first_name}."
    )

# Простой HTTP-сервер для Render
async def handle(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
