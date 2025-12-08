import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# --- Настройки ---
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

def get_arc_raiders_events_from_api_calculated():
    """Получает события из API MetaForge и вычисляет активные/предстоящие на основе расписания."""
    try:
        response = requests.get(EVENT_TIMERS_API_URL)
        response.raise_for_status()
        data = response.json()

        raw_events = data.get('data', [])
        active_events = []
        upcoming_events = []

        current_time_utc = datetime.now(timezone.utc) # <-- offset-aware
        current_date_utc = current_time_utc.date()
        current_time_only = current_time_utc.time()  # <-- offset-naive time object

        # Словарь для отслеживания ближайшего предстоящего окна для каждого (название, карта)
        next_upcoming_for_location = {}

        for event_obj in raw_events:
            name = event_obj.get('name', 'Unknown Event')
            location = event_obj.get('map', 'Unknown Location')
            times_list = event_obj.get('times', [])

            # Проходим по каждому временному окну события на этой карте
            for time_window in times_list:
                start_str = time_window.get('start') # Например, "01:00"
                end_str = time_window.get('end')     # Например, "02:00"

                if not start_str or not end_str:
                    logger.warning(f"Missing start or end time for event {name} at {location}")
                    continue

                try:
                    # Парсим время из строки "HH:MM" в объект time
                    start_time = datetime.strptime(start_str, '%H:%M').time() # <-- offset-naive time object
                    end_time = datetime.strptime(end_str, '%H:%M').time()     # <-- offset-naive time object

                    # --- Вычисление активности ---
                    # Случай 1: start и end в один день (например, 01:00 - 02:00)
                    if start_time <= end_time:
                        if start_time <= current_time_only < end_time:
                            # Событие активно сегодня
                            # Вычисляем время окончания как datetime объект (на сегодня, в UTC)
                            # datetime.combine создает offset-naive datetime, нужно сделать его aware
                            end_datetime_naive = datetime.combine(current_date_utc, end_time)
                            end_datetime = end_datetime_naive.replace(tzinfo=timezone.utc) # <-- offset-aware

                            # Если end_datetime <= current_time_utc (например, из-за секунд/миллисекунд), добавляем день
                            if end_datetime <= current_time_utc:
                                logger.warning(f"End time {end_datetime} is <= current time {current_time_utc}, adding 1 day.")
                                end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), end_time)
                                end_datetime = end_datetime_naive.replace(tzinfo=timezone.utc)

                            time_left = end_datetime - current_time_utc # <-- Теперь оба aware
                            total_seconds = int(time_left.total_seconds())
                            hours, remainder = divmod(total_seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            time_parts = []
                            if hours > 0: time_parts.append(f"{hours}h")
                            if minutes > 0: time_parts.append(f"{minutes}m")
                            if seconds > 0 or not time_parts: time_parts.append(f"{seconds}s")
                            time_left_str = " ".join(time_parts)

                            active_events.append({
                                'name': name,
                                'location': location,
                                'time_left': time_left_str,
                                'end_time': end_datetime
                            })
                            logger.info(f"Добавлено активное событие (сегодня): {name} на {location}, осталось {time_left_str}")
                            # Переходим к следующему окну, т.к. активное уже найдено для этого (name, location)
                            continue

                    # Случай 2: start > end (например, 23:00 - 01:00 -> событие пересекает полночь)
                    else: # start_time > end_time
                        if (current_time_only >= start_time) or (current_time_only < end_time):
                            # Событие активно сегодня или перешло на завтра
                            # Вычисляем время окончания
                            # Если текущее время >= start_time, значит событие началось сегодня и закончится завтра
                            if current_time_only >= start_time:
                                end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), end_time)
                            else: # current_time_only < end_time -> событие началось вчера и заканчивается сегодня
                                end_datetime_naive = datetime.combine(current_date_utc, end_time)

                            end_datetime = end_datetime_naive.replace(tzinfo=timezone.utc) # <-- offset-aware
                            time_left = end_datetime - current_time_utc # <-- Теперь оба aware
                            total_seconds = int(time_left.total_seconds())
                            hours, remainder = divmod(total_seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            time_parts = []
                            if hours > 0: time_parts.append(f"{hours}h")
                            if minutes > 0: time_parts.append(f"{minutes}m")
                            if seconds > 0 or not time_parts: time_parts.append(f"{seconds}s")
                            time_left_str = " ".join(time_parts)

                            active_events.append({
                                'name': name,
                                'location': location,
                                'time_left': time_left_str,
                                'end_time': end_datetime
                            })
                            logger.info(f"Добавлено активное событие (переходящее): {name} на {location}, осталось {time_left_str}")
                            continue # Переходим к следующему окну


                    # --- Вычисление предстоящего ---
                    # Если не активно, ищем ближайшее время начала
                    # Случай 1: start и end в один день (например, 01:00 - 02:00)
                    if start_time <= end_time:
                        if start_time > current_time_only: # Начнётся сегодня
                            start_datetime_naive = datetime.combine(current_date_utc, start_time)
                        else: # Началось сегодня, но уже прошло, ищем на завтра
                            start_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), start_time)
                    # Случай 2: start > end (например, 23:00 - 01:00)
                    else: # start_time > end_time
                        if current_time_only < start_time and current_time_only >= end_time: # Событие еще не началось сегодня (например, 22:00, а старт в 23:00)
                            start_datetime_naive = datetime.combine(current_date_utc, start_time)
                        else: # Событие уже прошло сегодня, ищем на завтра или позже
                            start_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), start_time)

                    # Сделать start_datetime aware
                    start_datetime = start_datetime_naive.replace(tzinfo=timezone.utc) # <-- offset-aware

                    time_to_start = start_datetime - current_time_utc # <-- Теперь оба aware
                    total_seconds = int(time_to_start.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_parts = []
                    if hours > 0: time_parts.append(f"{hours}h")
                    if minutes > 0: time_parts.append(f"{minutes}m")
                    if seconds > 0 or not time_parts: time_parts.append(f"{seconds}s")
                    time_to_start_str = " ".join(time_parts)

                    # Проверяем, является ли это окно ближайшим для данной пары (name, location)
                    key = (name, location)
                    if key not in next_upcoming_for_location or start_datetime < next_upcoming_for_location[key]['start_time']:
                        next_upcoming_for_location[key] = {
                            'time_left': time_to_start_str,
                            'start_time': start_datetime # <-- Убедиться, что это aware
                        }
                        logger.info(f"Найдено предстоящее событие для {name} на {location}, начнётся через {time_to_start_str} ({start_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')})")

                except ValueError as e:
                    logger.error(f"Error parsing time for event {name} at {location}: {start_str}, {end_str}. Error: {e}")

        # После обработки всех событий, добавляем ближайшие предстоящие из словаря
        for (name, location), event_info in next_upcoming_for_location.items():
             upcoming_events.append({
                 'name': name,
                 'location': location,
                 'time_left': event_info['time_left'],
                 'start_time': event_info['start_time'] # <-- Должно быть aware
             })

        # Сортируем предстоящие события по времени начала
        # Сортировка будет корректной, так как start_time теперь aware
        upcoming_events.sort(key=lambda x: x['start_time'])

        logger.info(f"Вычисление по API завершено: {len(active_events)} активных, {len(upcoming_events)} предстоящих.")
        return active_events, upcoming_events

    except requests.RequestException as e:
        logger.error(f"Ошибка при получении данных из API: {e}")
        return [], []
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке данных из API: {e}")
        return [], []

# --- Обработчики команд и кнопок ---
# (Код обработчиков остаётся без изменений, меняется только функция получения данных)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="События ARC Raiders", callback_data="events")]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}! Нажми кнопку ниже, чтобы посмотреть активные и предстоящие события в ARC Raiders.",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == 'events')
async def process_callback_events(callback_query: types.CallbackQuery):
    await send_events_message(callback_query.message)
    await callback_query.answer()

async def send_events_message(message: types.Message):
    # Вызываем НОВУЮ функцию получения данных из API с вычислением
    active, upcoming = get_arc_raiders_events_from_api_calculated()

    response_text = format_event_message(active, "active")
    response_text += "\n" + format_event_message(upcoming, "upcoming")

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="events")]
    ])

    await message.answer(response_text, reply_markup=keyboard, parse_mode='Markdown')

def format_event_message(events, event_type="active"):
    if not events:
        return f"Нет {'активных' if event_type == 'active' else 'предстоящих'} событий.\n"

    header = "Активные события:\n" if event_type == "active" else "Предстоящие события:\n"
    message = header
    for event in events:
        if event_type == "active":
            message += f"- **{event['name']}** на карте **{event['location']}** (осталось: {event['time_left']})\n"
        else:
            message += f"- **{event['name']}** на карте **{event['location']}** (начнётся через: {event['time_left']})\n"
    return message

async def main():
    logger.info("Запуск бота с использованием вычисленного таймера из API...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
