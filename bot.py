import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext  # <-- Импортирован FSMContext
from aiogram.fsm.state import State, StatesGroup  # <-- Импортирован StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- Добавляем класс состояний для обратной связи ---
class Feedback(StatesGroup):
    waiting_for_message = State()

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

# Укажите ваш Telegram ID (число), чтобы получать сообщения. Найти можно, например, через @userinfobot
YOUR_TELEGRAM_ID = 123456789 # ЗАМЕНИТЕ НА СВОЙ ЧИСЛОВОЙ ID

# Убран лишний пробел в конце URL
EVENT_TIMERS_API_URL = 'https://metaforge.app/api/arc-raiders/event-timers' # <-- Исправлено: убран пробел

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Инициализация бота ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage() # Используем MemoryStorage, как и раньше
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
    # Новые события из JSON
    "Cold Snap": "Холодная вспышка",
    "Locked Gate": "Закрытые врата",
}

MAP_TRANSLATIONS = {
    "Dam": "Дамба",
    "Buried City": "Погребенный город",
    "Spaceport": "Космопорт",
    "Blue Gate": "Синие врата",
    "Stella Montis": "Стелла Монти",
}

# --- Ссылки для кнопок ---
# Убраны лишние пробелы в конце URL
LINKS = {
    "streams": "https://www.twitch.tv/silovik_",  # Замените на реальную ссылку
    "telegram": "https://t.me/silovik_stream", # Пример, замените на реальную ссылку
    "support": "https://dalink.to/silovik_", # Пример, замените на реальную ссылку
    # "update": "https://www.arcraiders.com/patch-notes", # Убрана, так как теперь текст
}

# --- Текст для обновления игры ---
# Впишите сюда текст, который будет отправляться при нажатии кнопки "Обновление игры"
GAME_UPDATE_TEXT = """
<strong>КРУПНОЕ ОБНОВЛЕНИЕ 1.7.0 В ARC RAIDERS!</strong> (11.12.2025)

🔉 <strong>Обновление 1.7.0:</strong>
-Если кратко добавили:

🌟Условие карты «Заморозки»;
🌟Событие «Мерцающее огоньки»;
🌟Новая бесплатная колода рейдеров «Вратарь» — появится 26 декабря;
🌟Новые задания и предметы;
🌟Добавлена функция сброса дерева навыков.

Другие моменты патча:

🌟Добавлен альтернативный вариант прицеливания (переключение вместо удержания).
🌟В кошельке теперь отображается лимит кредитов (800).
🌟Различные праздничные предметы, которые помогут вам проникнуться духом праздника.
🌟Чертёж Афелия теперь выпадает на карте Стелле Монтис, больше не выпадает из Матриарха.
🌟Добавлена кастомизация инструмента рейдера.
🌟Исправлены различные проблемы с коллизиями на картах.
🌟Улучшена проверка расстояния до точки появления в Стелле Монтис, чтобы решить проблему, когда игроки появляются слишком близко друг к другу.

Изменения баланса оружия:

Беттина - (Скорость снижения прочности снижена с ~0,43 % до ~0,17 % за выстрел, на практике для полного исчерпания прочности требовалось около 12 полных магазинов, но теперь для этого нужно 26 (с учётом увеличенного размера магазина), размер базового магазина увеличен с 20 до 22, время перезарядки уменьшено с 5 до 4,5).

Эти изменения направлены на то, чтобы сделать Беттину менее зависимой от дополнительного оружия. Теперь это оружие должно быть более эффективным в PvP, но не слишком. Данные показывают, что это оружие по-прежнему является одним из самых эффективных в PvE при своей редкости. 

Трещётка - (Размер базового магазина увеличен с 10 до 12).
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
            # В новом API times нет, вместо этого startTime и endTime
            start_timestamp_ms = event_obj.get('startTime')
            end_timestamp_ms = event_obj.get('endTime')

            if not start_timestamp_ms or not end_timestamp_ms:
                logger.warning(f"Missing start or end timestamp for event {name} at {location}")
                continue

            try:
                # Конвертируем миллисекунды в datetime объект (в UTC)
                start_dt = datetime.fromtimestamp(start_timestamp_ms / 1000, tz=timezone.utc)
                end_dt = datetime.fromtimestamp(end_timestamp_ms / 1000, tz=timezone.utc)

                # --- Вычисление активности ---
                # Событие активно, если текущее время попадает в интервал [start_dt, end_dt)
                if start_dt <= current_time_utc < end_dt:
                    # Вычисляем оставшееся время до окончания
                    time_left = end_dt - current_time_utc
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
                        'end_time': end_dt
                    })
                    logger.info(f"Добавлено активное событие (по времени): {name} на {location}, осталось {time_left_str}")
                    # Переходим к следующему событию, т.к. активное уже найдено для этого (name, location)
                    continue

                # --- Вычисление предстоящего ---
                # Если не активно, проверяем, является ли это окно ближайшим предстоящим
                # Событие предстоит, если его start_dt > current_time_utc
                if start_dt > current_time_utc:
                    # Вычисляем время до начала
                    time_to_start = start_dt - current_time_utc
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
                    if key not in next_upcoming_for_location or start_dt < next_upcoming_for_location[key]['start_time']:
                        next_upcoming_for_location[key] = {
                            'time_left': time_to_start_str,
                            'start_time': start_dt # <-- Убедиться, что это aware
                        }
                        logger.info(f"Найдено предстоящее событие для {name} на {location}, начнётся через {time_to_start_str} ({start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')})")

            except ValueError as e:
                logger.error(f"Error parsing timestamp for event {name} at {location}: {start_timestamp_ms}, {end_timestamp_ms}. Error: {e}")
                continue # Переходим к следующему событию
            except Exception as e:
                logger.error(f"Unexpected error processing time for event {name} at {location}: {start_timestamp_ms}, {end_timestamp_ms}. Error: {e}")
                continue # Переходим к следующему событию

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
    logger.info("Вызов send_events_message")
    active, upcoming = get_arc_raiders_events_from_api_calculated()
    logger.info(f"Получено из API: {len(active)} активных, {len(upcoming)} предстоящих.")

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
    logger.info("Обработка callback 'refresh_events'") # <-- ДОБАВЛЕНО ЛОГИРОВАНИЕ
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
             return f"Нет активных событий.\n"
        else: # Для предстоящих, если список пуст, просто не выводим заголовок
             return "" # или f"Нет предстоящих событий в ближайшее время.\n" если нужно сообщение

    # Выбираем заголовок с эмодзи
    # parse_mode='HTML', так что используем теги
    header = "<strong>🟢 Активные события:</strong>\n" if event_type == "active" else "<strong>🔴 Предстоящие события:</strong>\n"
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
    logger.info("Запуск бота с использованием вычисленного таймера из API (все предстоящие), кнопками ссылок, текстом об обновлении, редактированием сообщений и формой обратной связи...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
