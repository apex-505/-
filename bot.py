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
from aiogram.types import Message, ChatPermissions

TOKEN = "8844473296:AAHZ0qrpucOehAFnNFNWNSvnZ5ae9emJewA"

dp = Dispatcher()

# Инициализация базы данных (баллы, кулдаун и система варнов)
def init_db():
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    # Таблица для очков дружбы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendship (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER,
            last_time REAL
        )
    ''')
    # Таблица для варнов (предупреждений)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            reason TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Парсинг времени для мута (например: 10m, 2h, 1d)
def parse_time(time_str: str) -> int:
    unit = time_str[-1].lower()
    try:
        val = int(time_str[:-1])
    except ValueError:
        return 0
    
    if unit == 's':
        return val
    elif unit == 'm':
        return val * 60
    elif unit == 'h':
        return val * 3600
    elif unit == 'd':
        return val * 86400
    return 0

@dp.message(F.text.lower().in_({"/start", ".start", "/help", ".помощь"}))
async def cmd_help(message: Message):
    await message.answer(
        "🤖 <b>Список доступных команд:</b>\n\n"
        "🤗 <b>Развлечения:</b>\n"
        "• <code>.почесать</code> — получить баллы дружбы (раз в 4 часа)\n"
        "• <code>.баланс</code> — посмотреть свой счет\n\n"
        "🛡 <b>Администрирование (только ответ на сообщение):</b>\n"
        "• <code>.мут [время]</code> — замутить (например: <code>.мут 10m</code> или <code>.мут 1h</code>)\n"
        "• <code>.размут</code> — снять мут\n"
        "• <code>.бан</code> — заблокировать пользователя\n"
        "• <code>.разбан</code> — разблокировать (нужно ответить или знать ID)\n"
        "• <code>.варн [причина]</code> — выдать предупреждение\n"
        "• <code>.варны</code> — посмотреть список варнов пользователя"
    )

# Команда .почесать с кулдауном 4 часа
@dp.message(F.text.lower().in_({".почесать", "/pochesat"}))
async def cmd_pochesat(message: Message):
    user = message.from_user
    current_time = time.time()
    cooldown = 4 * 60 * 60  # 4 часа в секундах
    
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT points, last_time FROM friendship WHERE user_id = ?', (user.id,))
    row = cursor.fetchone()
    
    if row is not None:
        points, last_time = row
        time_diff = current_time - last_time
        if time_diff < cooldown:
            timeLeft = int(cooldown - time_diff)
            hours = timeLeft // 3600
            minutes = (timeLeft % 3600) // 60
            conn.close()
            await message.answer(
                f"⏳ @{user.username or user.first_name}, ты уже чесал карму недавно! "
                f"Следующий раз будет доступен через <b>{hours} ч. {minutes} мин.</b>"
            )
            return
    
    earned_points = random.randint(1, 10)
    
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

@dp.message(F.text.lower().in_({".баланс", "/balans"}))
async def cmd_balans(message: Message):
    user = message.from_user
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('SELECT points FROM friendship WHERE user_id = ?', (user.id,))
    row = cursor.fetchone()
    conn.close()
    
    points = row[0] if row else 0
    await message.answer(f"📊 У тебя на счету <b>{points}</b> балл(ов) дружбы.")

# 🔇 МУТ (.мут [время], например: .мут 10m)
@dp.message(F.text.lower().startswith((".мут", "/mute")))
async def cmd_mute(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Эту команду нужно вызывать ответом на сообщение нарушителя!")
        return
    
    args = message.text.split()
    duration_str = args[1] if len(args) > 1 else "1h"  по умолчанию на 1 час
    seconds = parse_time(duration_str)
    
    if seconds == 0:
        await message.answer("⚠️ Неверный формат времени! Используйте: <code>.мут 30s</code>, <code>.мут 10m</code>, <code>.мут 2h</code> или <code>.мут 1d</code>")
        return

    target_user = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    try:
        until_date = int(time.time() + seconds)
        await message.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await message.answer(f"🔇 Пользователь @{target_user.username or target_user.first_name} замучен на <b>{duration_str}</b>.")
    except Exception as e:
        await message.answer(f"❌ Ошибка! Убедитесь, что бот — администратор с правами банить.")

# 🔊 РАЗМУТ (.размут)
@dp.message(F.text.lower().in_({".размут", "/unmute"}))
async def cmd_unmute(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя, чтобы снять мут!")
        return
    
    target_user = message.reply_to_message.from_user
    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await message.answer(f"🔊 С пользователя @{target_user.username or target_user.first_name} снят мут.")
    except Exception as e:
        await message.answer("❌ Не удалось снять мут. Проверьте права бота.")

# 🔨 БАН (.бан)
@dp.message(F.text.lower().in_({".бан", "/ban"}))
async def cmd_ban(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя, которого нужно забанить!")
        return
    
    target_user = message.reply_to_message.from_user
    try:
        await message.bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.answer(f"🔨 Пользователь @{target_user.username or target_user.first_name} заблокирован.")
    except Exception as e:
        await message.answer("❌ Ошибка бана. Убедитесь, что у бота есть права администратора.")

# 🔓 РАЗБАН (.разбан [user_id])
@dp.message(F.text.lower().startswith((".разбан", "/unban")))
async def cmd_unban(message: Message):
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        await message.answer("⚠️ Укажите ID пользователя или ответьте на его сообщение: <code>.разбан ID</code>")
        return
    
    target_id = message.reply_to_message.from_user.id if message.reply_to_message else int(args[1])
    try:
        await message.bot.unban_chat_member(chat_id=message.chat.id, user_id=target_id, only_if_banned=True)
        await message.answer(f"🔓 Пользователь с ID <code>{target_id}</code> разбанен.")
    except Exception as e:
        await message.answer("❌ Ошибка разбана. Проверьте правильность ID и права бота.")

# ⚠️ ВАРН (.варн [причина])
@dp.message(F.text.lower().startswith((".варн", "/warn")))
async def cmd_warn(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя, чтобы выдать варн!")
        return
    
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Без причины"
    target_user = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warnings (user_id, chat_id, reason) VALUES (?, ?, ?)', (target_user.id, chat_id, reason))
    
    # Считаем общее количество варнов
    cursor.execute('SELECT COUNT(*) FROM warnings WHERE user_id = ? AND chat_id = ?', (target_user.id, chat_id))
    warn_count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    await message.answer(
        f"⚠️ Администратор выдал предупреждение пользователю @{target_user.username or target_user.first_name}.\n"
        f"📝 Причина: <b>{reason}</b>\n"
        f"📊 Всего варнов: <b>{warn_count}/3</b>"
    )
    
    # Авто-бан при достижении 3 варнов
    if warn_count >= 3:
        try:
            await message.bot.ban_chat_member(chat_id=chat_id, user_id=target_user.id)
            await message.answer(f"🚨 Пользователь @{target_user.username or target_user.first_name} автоматически забанен за 3 предупреждения!")
        except Exception:
            pass

# 📋 СПИСОК ВАРНОВ (.варны)
@dp.message(F.text.lower().in_({".варны", "/warnings"}))
async def cmd_warnings(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя, чтобы посмотреть его варны!")
        return
    
    target_user = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('SELECT reason FROM warnings WHERE user_id = ? AND chat_id = ?', (target_user.id, chat_id))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"✨ У пользователя @{target_user.username or target_user.first_name} нет предупреждений.")
        return
    
    text = f"📋 Список предупреждений пользователя @{target_user.username or target_user.first_name} ({len(rows)}):\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]}\n"
        
    await message.answer(text)

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
