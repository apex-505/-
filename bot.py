import asyncio
import logging
import sys
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
      f"🔇 Администратор @{admin.username or admin.first_name} замутил"
      f" пользователя @{target_user.username or target_user.first_name}."
  )


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
  if not message.reply_to_message:
    await message.answer(
        "Эту команду нужно вызывать ответом на сообщение нарушителя!"
    )
    return
  target_user = message.reply_to_message.from_user
  admin = message.from_user
  await message.answer(
      f"🔨 Администратор @{admin.username or admin.first_name} забанил"
      f" пользователя @{target_user.username or target_user.first_name}."
  )


@dp.message(Command("warn"))
async def cmd_warn(message: Message):
  if not message.reply_to_message:
    await message.answer(
        "Эту команду нужно вызывать ответом на сообщение нарушителя!"
    )
    return
  target_user = message.reply_to_message.from_user
  admin = message.from_user
  await message.answer(
      f"⚠️ Администратор @{admin.username or admin.first_name} выдал"
      f" предупреждение пользователю @{target_user.username or target_user.first_name}"
      " (1/3)."
  )


async def main():
  bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, stream=sys.stdout)
  asyncio.run(main())
