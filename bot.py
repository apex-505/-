import asyncio
import logging
import os
import urllib.parse
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import BufferedInputFile
from openai import OpenAI

# Свежие ключи
TELEGRAM_BOT_TOKEN = "8202376236:AAHnS6PDWQnKK7G0J0gHa575h12m2anUJYk"
OPENROUTER_API_KEY = "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"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

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
    await message.answer("Привет! Бот успешно запущен. Пиши вопросы или используй `/img <описание>` для картинок.")

@dp.message(Command("img"))
async def cmd_img(message: types.Message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt:
        await message.answer("Укажи описание после /img")
        return

    await message.answer("🎨 Генерирую изображение...")
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
    image_bytes = await download_image_as_bytes(image_url)
    
    if image_bytes:
        photo = BufferedInputFile(image_bytes, filename="image.jpg")
        await message.answer_photo(photo, caption=f"🖼 *{prompt}*", parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка генерации.")

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip() if message.text else ""
    
    if text.lower().startswith("нарисуй") or text.lower().startswith("создай картинку"):
        prompt = text
        for prefix in ["нарисуй", "создай картинку"]:
            if text.lower().startswith(prefix):
                prompt = text[len(prefix):].strip()
                break
        
        await message.answer("🎨 Генерирую изображение...")
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        image_bytes = await download_image_as_bytes(image_url)
        
        if image_bytes:
            photo = BufferedInputFile(image_bytes, filename="image.jpg")
            await message.answer_photo(photo, caption=f"🖼 *{prompt}*", parse_mode="Markdown")
        else:
            await message.answer("❌ Ошибка генерации.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="google/gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "Ты полезный и умный ассистент. Отвечай подробно и актуально."},
                {"role": "user", "content": text}
            ]
        )
        if response and response.choices:
            await message.answer(response.choices[0].message.content)
        else:
            await message.answer("Нет ответа.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

async def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.create_task(start_web_server())
    await asyncio.sleep(3)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())