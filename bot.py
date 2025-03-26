import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Проверка токена
if not TOKEN:
    raise ValueError("TOKEN не найден в .env файле!")

# Создаем бота и диспетчер
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# Регистрируем router в диспетчере
dp.include_router(router)

# Обработчик команды /start
@router.message(Command("start"))
async def welcome(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Курьерские услуги")],
            [KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="🛵 Стать курьером")]
        ],
        resize_keyboard=True
    )
    await message.answer("🚀 Добро пожаловать в Zudrason!", reply_markup=keyboard)

# Обработчик кнопки "📦 Курьерские услуги"
@router.message(lambda message: message.text == "📦 Курьерские услуги")
async def order_form(message: types.Message):
    await message.answer("Отправьте адрес отправителя")

# Функция запуска бота
async def main():
    await dp.start_polling(bot)

# Запуск бота
if __name__ == "__main__":
    asyncio.run(main())