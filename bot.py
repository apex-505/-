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

# Инициализация базы данных
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

# Парсинг времени для мута
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

# Функция для проверки, является ли пользователь администратором чата
async def is_user_admin(message: Message) -> bool:
    # Создателя бота или личные сообщения можно пропустить, но для групп проверяем права:
    if message.chat.type == "private":
        return True
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        # Проверяем, создатель ли чата (creator) или администратор (administrator)
        if member.status in ["creator", "administrator"]:
            return True
    except Exception:
        pass
    return False

# Функция для поиска целевого пользователя
async def get_target_user(message: Message, args: list):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    if len(args) > 0:
        try:
            user_id = int(args[0])
            chat_member = await message.bot.get_chat_member(message.chat.id, user_id)
            return chat_member.user
        except Exception:
            return None
    return None

# 📜 КОМАНДА СО СПИСКОМ КОМАНД (.команды)
@dp.message(F.text.lower().in_({".команды", "/commands", "/help", ".помощь", "/start", ".start"}))
async def cmd_list(message: Message):
    await message.answer(
        "🤖 <b>Полный список команд бота:</b>\n\n"
        "🤗 <b>Развлечения и карма:</b>\n"
        "• <code>.почесать</code> — получить баллы дружбы (раз в 4 часа)\n"
        "• <code>.баланс</code> — посмотреть свой текущий счет\n\n"
        "👑 <b>Управление баллами (только для админов чата):</b>\n"
        "• <code>.датьбаллы [число]</code> — начислить баллы ответом на сообщение\n"
        "• <code>.установитьбаллы [число]</code> — точный баланс игрока\n\n"
        "🛡 <b>Администрирование чата (только для админов чата):</b>\n"
        "• <code>.мут [время]</code> — замутить (например: <code>.мут 10m</code>)\n"
        "• <code>.размут</code> — снять мут\n"
        "• <code>.бан</code> — заблокировать\n"
        "• <code>.разбан [ID]</code> — разблокировать по ID\n"
        "• <code>.варн [причина]</code> — выдать варн\n"
        "• <code>.варны</code> — список варнов"
    )

# Команда .почесать
@dp.message(F.text.lower().in_({".почесать", "/pochesat"}))
async def cmd_pochesat(message: Message):
    user = message.from_user
    current_time = time.time()
    cooldown = 4 * 60 * 60  # 4 часа
    
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
                f"⏳ @{user.username or user.first_name}, ты уже чесал карму! "
                f"Подожди еще <b>{hours} ч. {minutes} мин.</b>"
            )
            return
    
    earned_points = random.randint(1, 10)
    
    if row is None:
        cursor.execute('INSERT INTO friendship (user_id, username, points, last_time) VALUES (?, ?, ?, ?)', 
                       (user.id, user.username or user.first_name, earned_points, current_time))
        total_points = earned_points
    else:
        total_points = row[0] + earned_points
        cursor.execute('UPDATE friendship SET points = ?, last_time = ? WHERE user_id = ?', 
                       (total_points, current_time, user.id))
        
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

# 💎 ВЫДАТЬ БАЛЛЫ
@dp.message(F.text.lower().startswith((".датьбаллы", "/addpoints")))
async def cmd_add_points(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return
        
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя, которому хотите начислить баллы!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите количество баллов: <code>.датьбаллы 1000000</code>")
        return
    
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("⚠️ Укажите корректное число!")
        return
        
    target_user = message.reply_to_message.from_user
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT points FROM friendship WHERE user_id = ?', (target_user.id,))
    row = cursor.fetchone()
    
    if row is None:
        total_points = amount
        cursor.execute('INSERT INTO friendship (user_id, username, points, last_time) VALUES (?, ?, ?, ?)', 
                       (target_user.id, target_user.username or target_user.first_name, total_points, 0))
    else:
        total_points = row[0] + amount
        cursor.execute('UPDATE friendship SET points = ? WHERE user_id = ?', (total_points, target_user.id))
        
    conn.commit()
    conn.close()
    
    await message.answer(
        f"💎 Администратор начислил пользователю @{target_user.username or target_user.first_name} <b>+{amount}</b> баллов!\n"
        f"📊 Новый баланс: <b>{total_points}</b>"
    )

# 🛠 УСТАНОВИТЬ БАЛЛЫ
@dp.message(F.text.lower().startswith((".установитьбаллы", "/setpoints")))
async def cmd_set_points(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите точное число: <code>.установитьбаллы 1000000</code>")
        return
    
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("⚠️ Укажите корректное число!")
        return
        
    target_user = message.reply_to_message.from_user
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT points FROM friendship WHERE user_id = ?', (target_user.id,))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute('INSERT INTO friendship (user_id, username, points, last_time) VALUES (?, ?, ?, ?)', 
                       (target_user.id, target_user.username or target_user.first_name, amount, 0))
    else:
        cursor.execute('UPDATE friendship SET points = ? WHERE user_id = ?', (amount, target_user.id))
        
    conn.commit()
    conn.close()
    
    await message.answer(
        f"⚙️ Баланс пользователя @{target_user.username or target_user.first_name} успешно изменен на <b>{amount}</b> баллов!"
    )

# 🔇 МУТ
@dp.message(F.text.lower().startswith((".мут", "/mute")))
async def cmd_mute(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    args = message.text.split()
    target_user = None
    duration_str = "1h"
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if len(args) > 1:
            duration_str = args[1]
    elif len(args) > 2:
        try:
            user_id = int(args[1])
            chat_member = await message.bot.get_chat_member(message.chat.id, user_id)
            target_user = chat_member.user
            duration_str = args[2]
        except Exception:
            pass
    elif len(args) == 2 and not message.reply_to_message:
        duration_str = args[1]

    if not target_user and not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение нарушителя или укажите его ID для мута!")
        return
    
    if not target_user:
        target_user = message.reply_to_message.from_user

    seconds = parse_time(duration_str)
    if seconds == 0:
        await message.answer("⚠️ Неверный формат времени! Пример: <code>.мут 10m</code> или <code>.мут 2h</code>")
        return

    try:
        until_date = int(time.time() + seconds)
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await message.answer(f"🔇 Пользователь @{target_user.username or target_user.first_name} замучен на <b>{duration_str}</b>.")
    except Exception:
        await message.answer("❌ Ошибка! Убедитесь, что бот — администратор с правами.")

# 🔊 РАЗМУТ
@dp.message(F.text.lower().in_({".размут", "/unmute"}))
async def cmd_unmute(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    target_user = await get_target_user(message, message.text.split()[1:])
    if not target_user:
        await message.answer("⚠️ Ответьте на сообщение пользователя или укажите его ID, чтобы снять мут!")
        return
    
    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
        )
        await message.answer(f"🔊 С пользователя @{target_user.username or target_user.first_name} снят мут.")
    except Exception:
        await message.answer("❌ Не удалось снять мут.")

# 🔨 БАН
@dp.message(F.text.lower().startswith((".бан", "/ban")))
async def cmd_ban(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    target_user = await get_target_user(message, message.text.split()[1:])
    if not target_user:
        await message.answer("⚠️ Ответьте на сообщение пользователя или укажите его ID для бана!")
        return
    
    try:
        await message.bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.answer(f"🔨 Пользователь @{target_user.username or target_user.first_name} заблокирован.")
    except Exception:
        await message.answer("❌ Ошибка бана. Проверьте права бота.")

# 🔓 РАЗБАН
@dp.message(F.text.lower().startswith((".разбан", "/unban")))
async def cmd_unban(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите ID пользователя: <code>.разбан 123456789</code>")
        return
    
    try:
        target_id = int(args[1])
        await message.bot.unban_chat_member(chat_id=message.chat.id, user_id=target_id, only_if_banned=True)
        await message.answer(f"🔓 Пользователь с ID <code>{target_id}</code> разбанен.")
    except ValueError:
        await message.answer("⚠️ Укажите корректный числовой ID пользователя!")
    except Exception:
        await message.answer("❌ Ошибка разбана.")

# ⚠️ ВАРН
@dp.message(F.text.lower().startswith((".варн", "/warn")))
async def cmd_warn(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    args = message.text.split(maxsplit=1)
    target_user = await get_target_user(message, args[1:] if len(args) > 1 else [])
    
    if not target_user and not message.reply_to_message:
        await message.answer("⚠️ Ответьте на сообщение пользователя или укажите его ID для варна!")
        return
    
    if not target_user:
        target_user = message.reply_to_message.from_user
        reason = args[1] if len(args) > 1 else "Нарушение правил"
    else:
        parts = message.text.split(maxsplit=2)
        reason = parts[2] if len(parts) > 2 else "Нарушение правил"

    chat_id = message.chat.id
    
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO warnings (user_id, chat_id, reason) VALUES (?, ?, ?)', (target_user.id, chat_id, reason))
    cursor.execute('SELECT COUNT(*) FROM warnings WHERE user_id = ? AND chat_id = ?', (target_user.id, chat_id))
    warn_count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    await message.answer(
        f"⚠️ @{target_user.username or target_user.first_name} получил предупреждение.\n"
        f"📝 Причина: <b>{reason}</b>\n"
        f"📊 Всего варнов: <b>{warn_count}/3</b>"
    )
    
    if warn_count >= 3:
        try:
            await message.bot.ban_chat_member(chat_id=chat_id, user_id=target_user.id)
            await message.answer(f"🚨 Пользователь @{target_user.username or target_user.first_name} автоматически забанен за 3 варна!")
        except Exception:
            pass

# 📋 ВАРНЫ
@dp.message(F.text.lower().startswith((".варны", "/warnings")))
async def cmd_warnings(message: Message):
    if not await is_user_admin(message):
        await message.answer("❌ Эта команда доступна только администраторам чата!")
        return

    target_user = await get_target_user(message, message.text.split()[1:])
    if not target_user:
        await message.answer("⚠️ Ответьте на сообщение пользователя или укажите его ID, чтобы посмотреть варны!")
        return
    
    chat_id = message.chat.id
    conn = sqlite3.connect('friends.db')
    cursor = conn.cursor()
    cursor.execute('SELECT reason FROM warnings WHERE user_id = ? AND chat_id = ?', (target_user.id, chat_id))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"✨ У пользователя @{target_user.username or target_user.first_name} нет предупреждений.")
        return
    
    text = f"📋 Варны пользователя @{target_user.username or target_user.first_name} ({len(rows)}):\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]}\n"
        
    await message.answer(text)

# HTTP-сервер для Render
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
