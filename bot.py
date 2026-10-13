import asyncio
import logging
import os
import urllib.parse
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile
from google import genai

# --- КОНФИГУРАЦИЯ ---
TELEGRAM_BOT_TOKEN = "8202376236:AAGi9ubyOn5DNwHVpGLwY1D04w0cVtKTmus"
GOOGLE_API_KEY = "ВСТАВЬ_СЮДА_СВОЙ_КЛЮЧ_AQ..."

# Инициализация клиента новой библиотеки
client = genai.Client(api_key=GOOGLE_API_KEY)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

BOT_USERNAME = ""

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER И UPTIMEROBOT ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Веб-сервер запущен на порту {port}")

# --- ЛОГИКА БОТА ---
async def download_image_as_bytes(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                return None
    except Exception:
        return None

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я работаю 24/7 в личных сообщениях и группах.")

@dp.message()
async def handle_message(message: types.Message):
    global BOT_USERNAME
    if not BOT_USERNAME:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username.lower()

    text = message.text.strip() if message.text else ""
    chat_type = message.chat.type
    
    if chat_type in ["group", "supergroup"]:
        is_mentioned = f"@{BOT_USERNAME}" in text.lower()
        is_reply_to_bot = (
            message.reply_to_message 
            and message.reply_to_message.from_user 
            and message.reply_to_message.from_user.username 
            and message.reply_to_message.from_user.username.lower() == BOT_USERNAME
        )
        if not is_mentioned and not is_reply_to_bot:
            return
        text = text.replace(f"@{BOT_USERNAME}", "").strip()

    text_lower = text.lower()

    # Генерация картинок
    if any(keyword in text_lower for keyword in ["нарисуй", "сгенерируй", "картинка", "фото"]):
        status_msg = await message.answer("⚡ Генерирую изображение...")
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
        
        prompt = text
        try:
            translation = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=f"Rewrite this user request into a detailed, photorealistic English image prompt: '{text}'. Output ONLY raw text."
            )
            if translation and translation.text:
                prompt = translation.text.strip()
        except Exception:
            pass

        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&realism=true&enhance=true"
        
        try:
            img_bytes = await download_image_as_bytes(image_url)
            if img_bytes:
                photo_file = BufferedInputFile(img_bytes, filename="generated.jpg")
                await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
                await message.answer_photo(photo=photo_file, caption=f"🎨 **Результат:** _{text}_", parse_mode="Markdown")
            else:
                await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
                await message.answer("Не удалось сгенерировать изображение.")
        except Exception:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            await message.answer("Произошла ошибка при отправке картинки.")
        return

    # Текстовый диалог
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=text
        )
        if response and response.text:
            await message.answer(response.text)
        else:
            await message.answer("Не удалось получить ответ.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.create_task(start_web_server())
    print("Веб-сервер запущен, ждем сброса старых сессий...")
    
    await asyncio.sleep(5)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот начал поллинг!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())