import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import re # Для регулярных выражений при парсинге
import requests
from bs4 import BeautifulSoup # Необходимо установить: pip install beautifulsoup4 lxml
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

EVENT_TIMERS_URL = 'https://metaforge.app/arc-raiders/event-timers'

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
    "Harvester": "Жнец",
    "Lush Blooms": "Цветущие заросли",
    "Matriarch": "Матриарх",
    "Night Raid": "Ночной налёт",
    "Uncovered Caches": "Обнаруженные тайники",
    "Launch Tower Loot": "Добыча с пусковой башни",
    "Hidden Bunker": "Скрытый бункер",
    "Husk Graveyard": "Кладбище коконов",
    "Prospecting Probes": "Геологические зонды",
}

MAP_TRANSLATIONS = {
    "Dam": "Плотина",
    "Buried City": "Закопанный город",
    "Spaceport": "Космопорт",
    "Blue Gate": "Синие врата",
    "Stella Montis": "Стелла Монти",
}

# --- Ссылки для кнопок ---
LINKS = {
    "streams": "https://www.twitch.tv/directory/game/ARC%20Raider",
    "telegram": "https://t.me/arcraiders", # Пример, замените на реальную ссылку
    "support": "https://www.arcraiders.com/support", # Пример, замените на реальную ссылку
    # "update": "https://www.arcraiders.com/patch-notes", # Убрана, так как теперь текст
}

# --- Текст для обновления игры ---
# Впишите сюда текст, который будет отправляться при нажатии кнопки "Обновление игры"
GAME_UPDATE_TEXT = """
**ВАЖНОЕ ОБНОВЛЕНИЕ ARC RAIDERS!** (10.12.2025)

🔥 **Новое событие: "Танец Огня"**
   - Доступно на карте "Космопорт".
   - Только для игроков 30+ уровня.
   - Награды: Редкие ARCs, Скины оружия.

🛠 **Исправления:**
   - Исправлена ошибка с пропажей добычи.
   - Улучшена стабильность серверов в Азии.

📅 Следующее обновление: 17.12.2025
"""

# --- Функции для получения и парсинга данных из HTML ---

def parse_time_string(time_str):
    """Преобразует строку времени (например, '8m 48s', '1h 8m 48s') в timedelta."""
    if not time_str:
        return timedelta(seconds=0)

    # Ищем часы, минуты и секунды в строке
    hours_match = re.search(r'(\d+)\s*h', time_str, re.IGNORECASE)
    minutes_match = re.search(r'(\d+)\s*m', time_str, re.IGNORECASE)
    seconds_match = re.search(r'(\d+)\s*s', time_str, re.IGNORECASE)

    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0

    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

def get_arc_raiders_events_from_html():
    """Получает и парсит события с HTML-страницы MetaForge."""
    try:
        response = requests.get(EVENT_TIMERS_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        active_events = []
        upcoming_events = []

        # Находим секции "Active now" и "Upcoming next"
        active_section = soup.find(string=re.compile(r"Active now", re.IGNORECASE))
        if active_section:
            active_section = active_section.parent.parent # Поднимаемся к родительскому div контейнера
            active_items = active_section.find_all('div', recursive=False)
            for item in active_items:
                 # Проверяем, содержит ли div информацию о событии (обычно содержит img и span)
                 if item.find('img') and item.find('span'):
                    event_text = item.get_text(strip=True)
                    # Регулярное выражение для извлечения: [Название] [Локация] Ends in [Время]
                    # Учитываем возможные пробелы между частями
                    match = re.search(r'([^(]+?)\s+([^(]+?)\s+Ends\s+in\s+([\d\w\s]+)', event_text, re.IGNORECASE)
                    if match:
                        name = match.group(1).strip()
                        location = match.group(2).strip()
                        time_left_str = match.group(3).strip()
                        time_left = parse_time_string(time_left_str)
                        # Вычисляем время окончания
                        end_time_utc = datetime.now(timezone.utc) + time_left
                        active_events.append({
                            'name': name,
                            'location': location,
                            'time_left': time_left_str,
                            'end_time': end_time_utc
                        })
                        logger.info(f"Добавлено активное событие из HTML: {name} на {location}, осталось {time_left_str}")

        upcoming_section = soup.find(string=re.compile(r"Upcoming next", re.IGNORECASE))
        if upcoming_section:
            upcoming_section = upcoming_section.parent.parent # Поднимаемся к родительскому div контейнера
            upcoming_items = upcoming_section.find_all('div', recursive=False)
            for item in upcoming_items:
                 # Проверяем, содержит ли div информацию о событие (обычно содержит img и span)
                 if item.find('img') and item.find('span'):
                    event_text = item.get_text(strip=True)
                    # Регулярное выражение для извлечения: [Название] [Локация] Starts in [Время]
                    match = re.search(r'([^(]+?)\s+([^(]+?)\s+Starts\s+in\s+([\d\w\s]+)', event_text, re.IGNORECASE)
                    if match:
                        name = match.group(1).strip()
                        location = match.group(2).strip()
                        time_to_start_str = match.group(3).strip()
                        time_to_start = parse_time_string(time_to_start_str)
                        # Вычисляем время начала
                        start_time_utc = datetime.now(timezone.utc) + time_to_start
                        upcoming_events.append({
                            'name': name,
                            'location': location,
                            'time_left': time_to_start_str,
                            'start_time': start_time_utc
                        })
                        logger.info(f"Добавлено предстоящее событие из HTML: {name} на {location}, начнётся через {time_to_start_str}")

        # Обработка сложных событий типа Electromagnetic Storm
        # Ищем div'ы после "Upcoming next", которые содержат заголовок (h4 или strong) и списки
        # Начинаем искать после контейнера "Upcoming next"
        if upcoming_section:
            sections_after_upcoming = upcoming_section.find_next_siblings('div')
            for section in sections_after_upcoming:
                title_elem = section.find(['h4', 'strong'])
                if title_elem:
                    event_name = title_elem.get_text(strip=True)
                    # Ищем "Starts in" в этом же div или ближайшем родителе
                    starts_in_match = re.search(r'Starts\s+in\s+([\d\w\s]+)', section.get_text(), re.IGNORECASE)
                    if starts_in_match:
                        time_to_start_str = starts_in_match.group(1).strip()
                        time_to_start = parse_time_string(time_to_start_str)
                        start_time_utc = datetime.now(timezone.utc) + time_to_start

                        # Ищем "Upcoming windows"
                        windows_header = section.find(string=re.compile(r"Upcoming windows", re.IGNORECASE))
                        if windows_header:
                            windows_list = windows_header.parent.find_next_sibling('div')
                            if windows_list:
                                window_items = windows_list.find_all('div', recursive=False)
                                for window_item in window_items:
                                    win_text = window_item.get_text(strip=True)
                                    # Регулярное выражение для извлечения: [Время] [Локация] \n in [Время]
                                    win_match = re.search(r'([\d:]+\s*[-–]\s*[\d:]+)\s+([^(]+?)\s+in\s+([\d\w\s]+)', win_text, re.IGNORECASE)
                                    if win_match:
                                        time_period = win_match.group(1).strip()
                                        location = win_match.group(2).strip()
                                        time_to_window_str = win_match.group(3).strip()
                                        time_to_window = parse_time_string(time_to_window_str)
                                        window_start_time = datetime.now(timezone.utc) + time_to_window

                                        # Добавляем каждое окно как отдельное предстоящее событие
                                        upcoming_events.append({
                                            'name': event_name,
                                            'location': location,
                                            'time_left': time_to_window_str,
                                            'start_time': window_start_time,
                                            'period': time_period
                                        })
                                        logger.info(f"Добавлено предстоящее окно сложного события из HTML: {event_name} на {location}, начнётся через {time_to_window_str}")

        # Сортировка предстоящих событий по времени начала
        # Это ключевой момент: все предстоящие события (включая "окна") сортируются по времени начала
        upcoming_events.sort(key=lambda x: x['start_time'])

        logger.info(f"Парсинг HTML завершён: {len(active_events)} активных, {len(upcoming_events)} предстоящих.")
        return active_events, upcoming_events

    except requests.RequestException as e:
        logger.error(f"Ошибка при получении данных с {EVENT_TIMERS_URL}: {e}")
        return [], []
    except Exception as e:
        logger.error(f"Ошибка при парсинге HTML: {e}")
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
    # Вызываем функцию получения данных из HTML
    active, upcoming = get_arc_raiders_events_from_html()

    # Форматируем активные события
    active_message = format_event_message(active, "active")
    # Форматируем ВСЕ предстоящие события (без ограничения), они уже отсортированы по времени начала
    upcoming_message = format_event_message(upcoming, "upcoming")

    # Объединяем сообщения
    response_text = active_message
    if upcoming: # Добавляем предстоящие, только если они есть
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

# --- Форматирование сообщения с переводом, без ограничения и с эмодзи ---
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
            # Добавляем период времени, если он есть (для сложных событий)
            time_period = f" ({event.get('period', '')})" if event.get('period') else ""
            message += f"- **{translated_name}** на карте **{translated_location}**{time_period} (начнётся через: {event['time_left']})\n"
    return message

# --- Основная функция запуска ---
async def main():
    logger.info("Запуск бота с использованием парсинга HTML, кнопками ссылок, текстом об обновлении и редактированием сообщений...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
