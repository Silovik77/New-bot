import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import re # Для регулярных выражений при парсинге
import requests
from bs4 import BeautifulSoup # pip install beautifulsoup4 lxml
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

# URL для парсинга
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
    "Harvester": "Сборщик",
    "Lush Blooms": "Повышенная растительность",
    "Matriarch": "Матриарх",
    "Night Raid": "Ночной рейд",
    "Uncovered Caches": "Обнаруженные тайники",
    "Launch Tower Loot": "Добыча с пусковой башни",
    "Hidden Bunker": "Скрытый бункер",
    "Husk Graveyard": "Кладбище ARC",
    "Prospecting Probes": "Геологические зонды",
    # Новые события из HTML
    "Cold Snap": "Холодная вспышка",
    "Locked Gate": "Закрытые врата",
    "Husk Graveyard": "Кладбище коконов", # Повтор, но для надёжности
    "Prospecting Probes": "Геологические зонды", # Повтор
    "Launch Tower Loot": "Добыча с пусковой башни", # Повтор
    "Uncovered Caches": "Обнаруженные тайники", # Повтор
    "Lush Blooms": "Повышенная растительность", # Повтор
    "Matriarch": "Матриарх", # Повтор
    "Night Raid": "Ночной рейд", # Повтор
    "Electromagnetic Storm": "Электромагнитная буря", # Повтор
    "Harvester": "Сборщик", # Повтор
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
        # Добавим User-Agent, чтобы не казаться ботом
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(EVENT_TIMERS_URL, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        active_events = []
        upcoming_events = []

        # Находим секции "Active now" и "Upcoming next"
        active_section = soup.find(string=re.compile(r"Active now", re.IGNORECASE))
        if active_section:
            active_container = active_section.parent.parent # Поднимаемся к родительскому div контейнера
            active_items = active_container.find_all('div', recursive=False) # Ищем непосредственные div'ы
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
                        # time_left_str - это строка из HTML, например, "8m 48s"
                        # Вычисляем время окончания
                        current_time_utc = datetime.now(timezone.utc)
                        time_left_delta = parse_time_string(time_left_str)
                        end_time_utc = current_time_utc + time_left_delta

                        active_events.append({
                            'name': name,
                            'location': location,
                            'time_left': time_left_str,
                            'end_time': end_time_utc
                        })
                        logger.info(f"Добавлено активное событие из HTML: {name} на {location}, осталось {time_left_str}")

        upcoming_section = soup.find(string=re.compile(r"Upcoming next", re.IGNORECASE))
        if upcoming_section:
            upcoming_container = upcoming_section.parent.parent # Поднимаемся к родительскому div контейнера
            upcoming_items = upcoming_container.find_all('div', recursive=False) # Ищем непосредственные div'ы
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
                        # time_to_start_str - это строка из HTML, например, "1h 8m 48s"
                        # Вычисляем время начала
                        current_time_utc = datetime.now(timezone.utc)
                        time_to_start_delta = parse_time_string(time_to_start_str)
                        start_time_utc = current_time_utc + time_to_start_delta

                        upcoming_events.append({
                            'name': name,
                            'location': location,
                            'time_left': time_to_start_str,
                            'start_time': start_time_utc
                        })
                        logger.info(f"Добавлено предстоящее событие из HTML: {name} на {location}, начнётся через {time_to_start_str} ({start_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')})")

        # Обработка сложных событий типа Electromagnetic Storm (если они есть в HTML в таком формате)
        # Ищем div'ы после "Upcoming next", которые содержат заголовок (h4 или strong) и списки
        sections_after_upcoming = upcoming_container.find_next_siblings('div') if upcoming_container else []
        for section in sections_after_upcoming:
            title_elem = section.find(['h4', 'strong'])
            if title_elem:
                event_name = title_elem.get_text(strip=True)
                # Ищем "Starts in" в этом же div или ближайшем родителе
                starts_in_match = re.search(r'Starts\s+in\s+([\d\w\s]+)', section.get_text(), re.IGNORECASE)
                if starts_in_match:
                    time_to_start_str = starts_in_match.group(1).strip()
                    time_to_start_delta = parse_time_string(time_to_start_str)
                    current_time_utc = datetime.now(timezone.utc)
                    start_time_utc = current_time_utc + time_to_start_delta

                    # Ищем "Upcoming windows"
                    windows_header = section.find(string=re.compile(r"Upcoming windows", re.IGNORECASE))
                    if windows_header:
                        windows_list = windows_header.parent.find_next_sibling('div')
                        if windows_list:
                            window_items = windows_list.find_all('div', recursive=False)
                            for window_item in window_items:
                                win_text = window_item.get_text(strip=True)
                                # Регулярное выражение для извлечения: [Время] [Локация] \n in [Время]
                                win_match = re.search(r'([\d:]+\s*[-–]\s*[\d:]+)\s+([^(]+)\s+in\s+([\d\w\s]+)', win_text, re.IGNORECASE)
                                if win_match:
                                    time_period = win_match.group(1).strip()
                                    location = win_match.group(2).strip()
                                    time_to_window_str = win_match.group(3).strip()
                                    time_to_window_delta = parse_time_string(time_to_window_str)
                                    # Вычисляем время начала *окна*
                                    window_start_time_utc = current_time_utc + time_to_window_delta

                                    upcoming_events.append({
                                        'name': event_name,
                                        'location': location,
                                        'time_left': time_to_window_str,
                                        'start_time': window_start_time_utc,
                                        'period': time_period # Добавляем период времени, если важно
                                    })
                                    logger.info(f"Добавлено предстоящее окно сложного события из HTML: {event_name} на {location}, начнётся через {time_to_window_str} ({window_start_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')})")

        # Сортировка предстоящих событий по времени начала
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
    # Клавиатура с кнопками в нужном порядке и с новыми названиями
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        # 1. События ARC Raiders
        [types.InlineKeyboardButton(text="События ARC Raiders", callback_data="events")],
        # 2. Обновление игры
        [types.InlineKeyboardButton(text="Обновление игры", callback_data="game_update_text")],
        # 3. Twitch
        [types.InlineKeyboardButton(text="Twitch", url=LINKS["streams"])], # Использует URL из словаря LINKS
        # 4. Телеграмм канал
        [types.InlineKeyboardButton(text="Телеграмм канал", url=LINKS["telegram"])], # Использует URL из словаря LINKS
        # 5. Обратная связь (ссылка)
        # ЗАМЕНИТЕ "https://t.me/Silovik_ttv" НА РЕАЛЬНУЮ ССЫЛКУ
        [types.InlineKeyboardButton(text="Обратная связь", url="https://t.me/Silovik_ttv")], # <-- Замените на вашу ссылку
        # 6. Поддержка бота
        [types.InlineKeyboardButton(text="Поддержка бота", url=LINKS["support"])], # Использует URL из словаря LINKS
    ])
    # Отправляем НОВОЕ сообщение с главным меню
    await message.answer(
        f"Привет, {message.from_user.first_name}! Выбери действие:",
        reply_markup=keyboard
    )

# Обработчик для обновления игры (ИЗМЕНЁН)
@dp.callback_query(lambda c: c.data == 'game_update_text')
async def process_callback_game_update(callback_query: types.CallbackQuery):
    # Создаём клавиатуру с кнопками "Назад" и "События"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        # <-- ПРОВЕРКА: callback_data="start_menu" (для возврата в главное меню)
        [types.InlineKeyboardButton(text="Назад", callback_data="start_menu")],
        # <-- ПРОВЕРКА: callback_data="events"
        [types.InlineKeyboardButton(text="События ARC Raiders", callback_data="events")]
    ])
    # Редактируем текущее сообщение (главное меню), заменяя его на текст обновления с новой клавиатурой
    try:
        await callback_query.message.edit_text(
            text=GAME_UPDATE_TEXT,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        logger.info("Сообщение обновления игры отредактировано.")
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение об обновлении: {e}. Отправляем новое.")
        # Если редактирование не удалось, отправим новое сообщение
        await callback_query.message.answer(
            text=GAME_UPDATE_TEXT,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    await callback_query.answer()

# Обработчик для событий (ИЗМЕНЁН)
@dp.callback_query(lambda c: c.data == 'events')
async def process_callback_events(callback_query: types.CallbackQuery):
    # Теперь вызываем send_events_message с edit=True
    # Это означает, что бот попытается ОТРЕДАКТИРОВАТЬ сообщение, в котором была нажата кнопка 'events'
    # (обычно это главное меню или меню обновления)
    await send_events_message(callback_query.message, edit=True)
    await callback_query.answer() # Отвечаем на callback_query

# Функция отправки или редактирования сообщения с событиями
async def send_events_message(message: types.Message, edit: bool = False):
    # <-- ДОБАВЛЕНО ЛОГИРОВАНИЕ -->
    logger.info("Вызов send_events_message (парсинг HTML)")
    active, upcoming = get_arc_raiders_events_from_html()
    logger.info(f"Получено из HTML: {len(active)} активных, {len(upcoming)} предстоящих.")

    # Форматируем активные события
    active_message = format_event_message(active, "active")
    # Форматируем ВСЕ предстоящие события (без ограничения)
    upcoming_message = format_event_message(upcoming, "upcoming")

    # Объединяем сообщения
    response_text = active_message
    if upcoming: # Добавляем предстоящие, только если они есть
        response_text += "\n" + upcoming_message

    # Клавиатура с кнопками "Обновить" и "Назад" (в главное меню)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        # <-- ПРОВЕРКА: callback_data="refresh_events"
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_events")],
        # <-- ПРОВЕРКА: callback_data="start_menu"
        [types.InlineKeyboardButton(text="Назад", callback_data="start_menu")]
    ])

    if edit:
        # Пытаемся отредактировать существующее сообщение
        try:
            # parse_mode изменён на HTML
            await message.edit_text(text=response_text, reply_markup=keyboard, parse_mode='HTML')
            logger.info("Сообщение с событиями отредактировано.")
        except Exception as e:
            # Если не получилось отредактировать (например, сообщение слишком старое), отправим новое
            logger.warning(f"Не удалось отредактировать сообщение: {e}. Отправляем новое.")
            # parse_mode изменён на HTML
            await message.answer(response_text, reply_markup=keyboard, parse_mode='HTML')
    else:
        # Отправляем новое сообщение
        # parse_mode изменён на HTML
        await message.answer(response_text, reply_markup=keyboard, parse_mode='HTML')

# Новый обработчик для обновления (редактирования) сообщения с событиями
@dp.callback_query(lambda c: c.data == 'refresh_events')
async def process_callback_refresh_events(callback_query: types.CallbackQuery):
    # Вызываем send_events_message с edit=True
    logger.info("Обработка callback 'refresh_events' (парсинг HTML)") # <-- ДОБАВЛЕНО ЛОГИРОВАНИЕ
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
    # Редактируем сообщение с событиями, заменяя его на главное меню
    # Для этого нужно получить клавиатуру главного меню
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        # <-- ПРОВЕРКА: callback_data="events"
        [types.InlineKeyboardButton(text="События ARC Raiders", callback_data="events")],
        [types.InlineKeyboardButton(text="Обновление игры", callback_data="game_update_text")],
        [types.InlineKeyboardButton(text="Twitch", url=LINKS["streams"])],
        [types.InlineKeyboardButton(text="Телеграмм канал", url=LINKS["telegram"])],
        [types.InlineKeyboardButton(text="Обратная связь", url="https://t.me/Silovik_ttv")], # <-- Замените на вашу ссылку
        [types.InlineKeyboardButton(text="Поддержка бота", url=LINKS["support"])],
    ])
    try:
        # Пытаемся отредактировать сообщение (список событий или обновление) и заменить его на главное меню
        await callback_query.message.edit_text(
            text=f"Привет, {callback_query.from_user.first_name}! Выбери действие:",
            reply_markup=keyboard
        )
        logger.info("Сообщение отредактировано: возврат в главное меню.")
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение для возврата в главное меню: {e}.")
        # Если редактировать не получилось, отправим новое сообщение с главным меню
        await callback_query.message.answer(
            f"Привет, {callback_query.from_user.first_name}! Выбери действие:",
            reply_markup=keyboard
        )
    await callback_query.answer() # Отвечаем на callback_query

# --- Форматирование сообщения с переводом, без ограничения и с эмодзи (HTML) ---
def format_event_message(events, event_type="active"):
    """Форматирует список событий в текстовое сообщение с переводом и эмодзи (HTML)."""
    if not events:
        # Если список пуст, возвращаем пустую строку или сообщение, только если это активные
        if event_type == "active":
             # parse_mode='HTML', так что используем теги
             return f"<b>🔴 Нет активных событий.</b>\n"
        else: # Для предстоящих, если список пуст, просто не выводим заголовок
             return "" # или f"<b>🟡 Нет предстоящих событий в ближайшее время.</b>\n" если нужно сообщение

    # Выбираем заголовок с эмодзи
    # parse_mode='HTML', так что используем теги
    header = "<b>🟢 Активные события:</b>\n" if event_type == "active" else "<b>🔴 Предстоящие события:</b>\n"
    message = header
    for event in events:
        # Получаем перевод или оставляем оригинальное имя, если перевод не найден
        translated_name = EVENT_TRANSLATIONS.get(event['name'], event['name'])
        translated_location = MAP_TRANSLATIONS.get(event['location'], event['location'])

        if event_type == "active":
            # parse_mode='HTML', используем теги <strong> и <em>
            # <em> для курсива, <strong> для жирного
            # translated_name будет курсивом, location - жирным
            message += f"- <em>{translated_name}</em> на карте <strong>{translated_location}</strong> (осталось: {event['time_left']})\n"
        else:
            # parse_mode='HTML', используем теги <strong>
            # translated_name и location будут жирными
            message += f"- <strong>{translated_name}</strong> на карте <strong>{translated_location}</strong> (начнётся через: {event['time_left']})\n"
    return message

# --- Основная функция запуска ---
async def main():
    logger.info("Запуск бота с использованием парсинга HTML, кнопками ссылок, текстом об обновлении, редактированием сообщений и формой обратной связи...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
