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

# --- Словари перевода ---
EVENT_TRANSLATIONS = {
    "Electromagnetic Storm": "Электромагнитная буря",
    "Harvester": "Сборщик",
    "Lush Blooms": "Повышенная растительность",
    "Matriarch": "Матриарх",
    "Night Raid": "Ночной рейд",
    "Uncovered Caches": "Обнаруженные тайники",
    "Launch Tower Loot": "Добыча с пусковой башни",
    "Hidden Bunker": "Скрытый бункер", # Добавлено из HTML
    "Husk Graveyard": "Кладбище коконов", # Добавлено из HTML
    "Prospecting Probes": "Геологические зонды", # Добавлено из HTML
}

MAP_TRANSLATIONS = {
    "Dam": "Плотина",
    "Buried City": "Погребенный город",
    "Spaceport": "Космопорт",
    "Blue Gate": "Синие врата",
    "Stella Montis": "Стелла Монти",
}

# --- Ссылки для кнопок ---
LINKS = {
    "streams": "https://www.twitch.tv/silovik_",
    "telegram": "https://t.me/silovik_stream", # Пример, замените на реальную ссылку
    "support": "https://dalink.to/silovik_", # Пример, замените на реальную ссылку

}

# --- Текст для обновления игры ---
# Впишите сюда текст, который будет отправляться при нажатии кнопки "Обновление игры"
GAME_UPDATE_TEXT = """
**Новое обновление ARC Raiders!**

- Добавлено новое событие: **Тестовое событие**.
- Изменены награды за **Ночной налёт**.
- Исправлены баги на карте **Плотина**.
- Улучшена стабильность серверов.

Дата выхода: 10 декабря 2025 года.
"""

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
                            if hours > 0: time_parts.append(f"{hours}ч")
                            if minutes > 0: time_parts.append(f"{minutes}м")
                            if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
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
                            if hours > 0: time_parts.append(f"{hours}ч")
                            if minutes > 0: time_parts.append(f"{minutes}м")
                            if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
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
                    if hours > 0: time_parts.append(f"{hours}ч")
                    if minutes > 0: time_parts.append(f"{minutes}м")
                    if seconds > 0 or not time_parts: time_parts.append(f"{seconds}с")
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение с основными кнопками."""
    # Клавиатура с кнопками "События", "Ссылки" и "Обновление игры" в главном меню
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="События ARC Raiders", callback_data="events")],
        [types.InlineKeyboardButton(text="📺 Стримы", url=LINKS["streams"])],
        [types.InlineKeyboardButton(text="💬 Телеграмм", url=LINKS["telegram"])],
        [types.InlineKeyboardButton(text="🆘 Поддержка", url=LINKS["support"])],
        [types.InlineKeyboardButton(text="🆕 Обновление игры", callback_data="game_update_text")]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}! Выбери действие:",
        reply_markup=keyboard
    )

# Обработчик для обновления игры
@dp.callback_query(lambda c: c.data == 'game_update_text')
async def process_callback_game_update(callback_query: types.CallbackQuery):
    await callback_query.message.answer(GAME_UPDATE_TEXT, parse_mode='Markdown')
    await callback_query.answer()

# Обработчик для событий
@dp.callback_query(lambda c: c.data == 'events')
async def process_callback_events(callback_query: types.CallbackQuery):
    await send_events_message(callback_query.message, edit=False) # Отправляем новое сообщение
    await callback_query.answer()

# Функция отправки или редактирования сообщения с событиями
async def send_events_message(message: types.Message, edit: bool = False):
    active, upcoming = get_arc_raiders_events_from_api_calculated()

    # Фильтруем предстоящие события по временному лимиту (например, 24 часа)
    current_time = datetime.now(timezone.utc)
    time_limit = current_time + timedelta(hours=24)
    filtered_upcoming = [event for event in upcoming if event['start_time'] <= time_limit]
    limited_upcoming = filtered_upcoming[:6] # Берём первые 6 из отфильтрованных

    active_message = format_event_message(active, "active")
    upcoming_message = format_event_message(limited_upcoming, "upcoming")

    response_text = active_message
    if limited_upcoming:
        response_text += "\n" + upcoming_message

    # Клавиатура с кнопками "Обновить" и "Назад" (в главное меню)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_events")], # Изменили callback
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_menu")]
    ])

    if edit:
        # Пытаемся отредактировать существующее сообщение
        try:
            await message.edit_text(text=response_text, reply_markup=keyboard, parse_mode='Markdown')
            logger.info("Сообщение с событиями отредактировано.")
        except Exception as e:
            # Если не получилось отредактировать (например, сообщение слишком старое), отправим новое
            logger.warning(f"Не удалось отредактировать сообщение: {e}. Отправляем новое.")
            await message.answer(response_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        # Отправляем новое сообщение
        await message.answer(response_text, reply_markup=keyboard, parse_mode='Markdown')

# Новый обработчик для обновления (редактирования) сообщения с событиями
@dp.callback_query(lambda c: c.data == 'refresh_events')
async def process_callback_refresh_events(callback_query: types.CallbackQuery):
    # Вызываем send_events_message с edit=True
    await send_events_message(callback_query.message, edit=True)
    # ВАЖНО: НЕ вызываем callback_query.answer() сразу, потому что edit_text может занять время
    # aiogram сам вызовет answer, если edit_text прошёл успешно.
    # Если edit_text не удался и было отправлено новое сообщение, answer нужно вызвать вручную.
    # Проверим, было ли сообщение отредактировано или отправлено новое.
    # Проще всего всегда вызвать answer, если edit_text не вызвал исключения.
    # Но если edit_text вызвал исключение и было отправлено новое сообщение,
    # то answer вызовет ошибку, так как callback уже "истек".
    # Обернём в try-except, чтобы избежать ошибки в последнем случае.
    try:
        await callback_query.answer()
    except Exception:
        pass # Игнорируем ошибку, если answer не нужен/невозможен

# Обработчик для кнопки "Назад" из меню событий
@dp.callback_query(lambda c: c.data == 'start_menu')
async def process_callback_back_to_start(callback_query: types.CallbackQuery):
    await cmd_start(callback_query.message)
    await callback_query.answer()

# --- Форматирование сообщения с переводом, ограничением и эмодзи ---
def format_event_message(events, event_type="active"):
    """Форматирует список событий в текстовое сообщение с переводом и эмодзи."""
    if not events:
        # Если список пуст, возвращаем пустую строку или сообщение, только если это активные
        if event_type == "active":
             return f"Нет активных событий.\n"
        else: # Для предстоящих, если список пуст, просто не выводим заголовок
             return "" # или f"Нет предстоящих событий в ближайшее время.\n" если нужно сообщение

    # Выбираем заголовок с эмодзи
    header = "🟢 Активные события:\n" if event_type == "active" else "🔴 Предстоящие события:\n"
    message = header
    for event in events:
        # Получаем перевод или оставляем оригинальное имя, если перевод не найден
        translated_name = EVENT_TRANSLATIONS.get(event['name'], event['name'])
        translated_location = MAP_TRANSLATIONS.get(event['location'], event['location'])

        if event_type == "active":
            message += f"- **{translated_name}** на карте **{translated_location}** (осталось: {event['time_left']})\n"
        else:
            message += f"- **{translated_name}** на карте **{translated_location}** (начнётся через: {event['time_left']})\n"
    return message

# --- Основная функция запуска ---
async def main():
    logger.info("Запуск бота с использованием вычисленного таймера из API, кнопками ссылок, текстом об обновлении и редактированием сообщений...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")

