import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = "8844473296:AAHZ0qrpucOehAFnNFNWNSvnZ5ae9emJewA"

dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я твой админ-бот. Дай мне права администратора в чате!"
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

# Простой HTTP-сервер, чтобы Render видел открытый порт и не выдавал ошибку тайм-аута
async def handle(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render передает порт через переменную окружения PORT, по умолчанию берем 8080
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Запускаем и веб-сервер для Render, и поллинг бота одновременно
    await web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
