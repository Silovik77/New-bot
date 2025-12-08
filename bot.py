import asyncio
import logging
from datetime import datetime, timezone
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# --- Настройки ---
# Вставьте сюда токен вашего Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

EVENT_TIMERS_API_URL = 'https://metaforge.app/api/arc-raiders/event-timers'

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Инициализация бота ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- Функции для получения и обработки данных из API ---

def get_arc_raiders_events_from_api():
    """Получает события из API MetaForge и анализирует их структуру."""
    try:
        response = requests.get(EVENT_TIMERS_API_URL)
        response.raise_for_status()
        data = response.json()

        raw_events = data.get('data', [])
        active_events = []
        upcoming_events = []

        current_time = datetime.now(timezone.utc)
        # Словарь для отслеживания ближайшего предстоящего окна для каждого события
        next_upcoming_for_event = {}

        for event_obj in raw_events:
            name = event_obj.get('name', 'Unknown Event')
            # Обработка 'map' как массива (хотя на сайте может быть строка, API может нормализовать)
            # В данном случае, мы будем использовать локации из 'windows', так как они точнее
            # possible_maps = event_obj.get('map', [])
            # if isinstance(possible_maps, str):
            #      possible_maps = [possible_maps]

            times_info = event_obj.get('times', {})
            windows = times_info.get('windows', [])

            # Проходим по каждому окну события
            for window in windows:
                start_str = window.get('startTime')
                end_str = window.get('endTime')
                location = window.get('location', 'Unknown Location')

                if not start_str or not end_str:
                    logger.warning(f"Missing startTime or endTime for event {name} at {location}")
                    continue

                try:
                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))

                    # Проверяем, активно ли окно *сейчас*
                    if start_time <= current_time < end_time:
                        time_left = end_time - current_time
                        # Форматируем оставшееся время как строку (например, "1h 23m 45s")
                        total_seconds = int(time_left.total_seconds())
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        # time_left_str = f"{hours}h {minutes}m {seconds}s"
                        # Убираем нули для красоты
                        time_parts = []
                        if hours > 0:
                            time_parts.append(f"{hours}h")
                        if minutes > 0:
                            time_parts.append(f"{minutes}m")
                        if seconds > 0 or not time_parts: # Показываем секунды, если это единственное значение или есть значение
                            time_parts.append(f"{seconds}s")
                        time_left_str = " ".join(time_parts)

                        active_events.append({
                            'name': name,
                            'location': location,
                            'time_left': time_left_str,
                            'end_time': end_time
                        })

                    # Проверяем, предстоит ли окно
                    elif start_time > current_time:
                        time_to_start = start_time - current_time
                        # Форматируем время до начала
                        total_seconds = int(time_to_start.total_seconds())
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        # time_to_start_str = f"{hours}h {minutes}m {seconds}s"
                        # Убираем нули для красоты
                        time_parts = []
                        if hours > 0:
                            time_parts.append(f"{hours}h")
                        if minutes > 0:
                            time_parts.append(f"{minutes}m")
                        if seconds > 0 or not time_parts: # Показываем секунды, если это единственное значение или есть значение
                            time_parts.append(f"{seconds}s")
                        time_to_start_str = " ".join(time_parts)

                        # Проверяем, является ли это окно ближайшим для данного события
                        # Сравниваем с уже найденным ближайшим
                        if name not in next_upcoming_for_event or start_time < next_upcoming_for_event[name]['start_time']:
                            next_upcoming_for_event[name] = {
                                'location': location,
                                'time_left': time_to_start_str,
                                'start_time': start_time
                            }
                except ValueError as e:
                    logger.error(f"Error parsing time for event {name}: {start_str}, {end_str}. Error: {e}")

        # После обработки всех окон, добавляем ближайшие предстоящие события
        # из словаря next_upcoming_for_event в список upcoming_events
        for name, event_info in next_upcoming_for_event.items():
             upcoming_events.append({
                 'name': name,
                 'location': event_info['location'],
                 'time_left': event_info['time_left'],
                 'start_time': event_info['start_time']
             })

        # Сортируем предстоящие события по времени начала
        upcoming_events.sort(key=lambda x: x['start_time'])

        # Логируем результаты для отладки
        logger.info(f"Found {len(active_events)} active events, {len(upcoming_events)} upcoming events.")
        return active_events, upcoming_events

    except requests.RequestException as e:
        logger.error(f"Ошибка при получении данных из API: {e}")
        return [], []
    except Exception as e:
        logger.error(f"Ошибка при обработке данных из API: {e}")
        return [], []

# --- Обработчики команд и кнопок ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение с кнопкой."""
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="События ARC Raiders", callback_data="events")]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}! Нажми кнопку ниже, чтобы посмотреть активные и предстоящие события в ARC Raiders.",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == 'events')
async def process_callback_events(callback_query: types.CallbackQuery):
    """Обрабатывает нажатие кнопки 'События'."""
    await send_events_message(callback_query.message)
    await callback_query.answer() # Убирает "часики" у кнопки

async def send_events_message(message: types.Message):
    """Отправляет сообщение с событиями."""
    # Вызываем функцию получения данных из API
    active, upcoming = get_arc_raiders_events_from_api()

    response_text = format_event_message(active, "active")
    response_text += "\n" + format_event_message(upcoming, "upcoming")

    # Клавиатура с кнопкой "Обновить"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="events")]
    ])

    await message.answer(response_text, reply_markup=keyboard, parse_mode='Markdown')

# --- Форматирование сообщения ---
def format_event_message(events, event_type="active"):
    """Форматирует список событий в текстовое сообщение."""
    if not events:
        return f"Нет {'активных' if event_type == 'active' else 'предстоящих'} событий.\n"

    header = "Активные события:\n" if event_type == "active" else "Предстоящие события:\n"
    message = header
    for event in events:
        if event_type == "active":
            # time_left_str уже вычислено в get_arc_raiders_events_from_api
            message += f"- **{event['name']}** на карте **{event['location']}** (осталось: {event['time_left']})\n"
        else:
            # time_left_str уже вычислено в get_arc_raiders_events_from_api
            message += f"- **{event['name']}** на карте **{event['location']}** (начнётся через: {event['time_left']})\n"
    return message

# --- Основная функция запуска ---
async def main():
    logger.info("Запуск бота с использованием API...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
