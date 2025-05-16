import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOSchedulerpip install -r requirements.txt

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализация планировщика
scheduler = AsyncIOScheduler()


# Состояния FSM
class ReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()


# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer(
        "Привет! Я бот-напоминалка. Чтобы создать напоминание, "
        "используй команду /remind\n\n"
        "Доступные форматы времени:\n"
        "1. Через сколько минут: +30 (через 30 минут)\n"
        "2. Время сегодня: 14:30\n"
        "3. Дата и время: 14:30 15.12.2023 или 14:30 15-12-2023"
    )


# Обработчик команды /remind
@dp.message_handler(commands=['remind'], state="*")
async def remind_command(message: types.Message):
    await message.answer("Напиши текст напоминания:")
    await ReminderStates.waiting_for_text.set()


# Обработчик текста напоминания
@dp.message_handler(state=ReminderStates.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['text'] = message.text

    await message.answer(
        "Теперь укажи время напоминания в одном из форматов:\n"
        "1. Через сколько минут: +30 (через 30 минут)\n"
        "2. Время сегодня: 14:30\n"
        "3. Дата и время: 14:30 15.12.2023 или 14:30 15-12-2023"
    )
    await ReminderStates.waiting_for_time.set()


# Функция для парсинга даты и времени
def parse_datetime(input_str: str) -> datetime:
    now = datetime.now()

    # Формат "+минуты" (например, +30)
    if re.match(r'^\+\d+$', input_str):
        minutes = int(input_str[1:])
        return now + timedelta(minutes=minutes)

    # Формат "ЧЧ:ММ" (например, 14:30)
    if re.match(r'^\d{1,2}:\d{2}$', input_str):
        hours, minutes = map(int, input_str.split(':'))
        reminder_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if reminder_time < now:
            reminder_time += timedelta(days=1)
        return reminder_time

    # Формат "ЧЧ:ММ ДД.ММ.ГГГГ" или "ЧЧ:ММ ДД-ММ-ГГГГ"
    datetime_match = re.match(r'^(\d{1,2}:\d{2})[\s](\d{1,2})[\.\-](\d{1,2})[\.\-](\d{4})$', input_str)
    if datetime_match:
        time_part, day, month, year = datetime_match.groups()
        hours, minutes = map(int, time_part.split(':'))
        day, month, year = map(int, (day, month, year))

        try:
            reminder_time = datetime(year=year, month=month, day=day, hour=hours, minute=minutes)
            if reminder_time < now:
                raise ValueError("Указанная дата уже прошла")
            return reminder_time
        except ValueError as e:
            raise ValueError(f"Некорректная дата: {e}")

    raise ValueError("Неизвестный формат времени")


# Обработчик времени напоминания
@dp.message_handler(state=ReminderStates.waiting_for_time)
async def process_time(message: types.Message, state: FSMContext):
    user_time = message.text.strip()
    chat_id = message.chat.id

    async with state.proxy() as data:
        reminder_text = data['text']

    try:
        reminder_time = parse_datetime(user_time)

        scheduler.add_job(
            send_reminder,
            'date',
            run_date=reminder_time,
            args=(chat_id, reminder_text)
        )

        await message.answer(
            f"⏰ Напоминание установлено на {reminder_time.strftime('%H:%M %d.%m.%Y')}:\n"
            f"{reminder_text}"
        )

    except ValueError as e:
        await message.answer(
            f"Ошибка: {str(e)}\n\n"
            "Пожалуйста, укажи время в одном из форматов:\n"
            "1. Через сколько минут: +30 (через 30 минут)\n"
            "2. Время сегодня: 14:30\n"
            "3. Дата и время: 14:30 15.12.2023 или 14:30 15-12-2023"
        )
        return

    await state.finish()


# Функция отправки напоминания
async def send_reminder(chat_id: int, text: str):
    await bot.send_message(chat_id, f"⏰ Напоминание:\n{text}")


# Запуск бота
if __name__ == '__main__':
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)