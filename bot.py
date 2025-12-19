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

# --- ИЗМЕНЁН URL API на events-schedule ---
EVENT_SCHEDULE_API_URL = 'https://metaforge.app/api/arc-raiders/events-schedule'

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
    # Новые события из JSON
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
    "Dam": "Дамба",
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
<strong>ВАЖНОЕ ОБНОВЛЕНИЕ ARC RAIDERS!</strong> (10.12.2025)

🔊 <strong>Информация:</strong>
-Разработчики Arc Raiders запустили опрос о картах
 Его можно пройти тут:
https://id.embark.games/id/arc-raiders/survey  
"""

# --- Функции для получения и обработки данных из API ---

def get_arc_raiders_events_from_api_schedule():
    """
    Получает события из API MetaForge (events-schedule) и вычисляет
    активные/предстоящие на основе ежедневного расписания HH:MM.
    """
    try:
        # --- ИЗМЕНЁН URL ЗАПРОСА ---
        response = requests.get(EVENT_SCHEDULE_API_URL)
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
            # --- ИЗМЕНЕНО: Получаем список times ---
            times_list = event_obj.get('times', [])

            # --- ИЗМЕНЕНО: Проходим по каждому временному окну события на этой карте ---
            for time_window in times_list:
                start_str = time_window.get('start') # Например, "01:00"
                end_str = time_window.get('end')     # Например, "02:00" или "24:00"

                if not start_str or not end_str:
                    logger.warning(f"Missing start or end time for event {name} at {location}")
                    continue

                try:
                    # Парсим время начала
                    start_time = datetime.strptime(start_str, '%H:%M').time() # <-- offset-naive time object

                    # --- ИСПРАВЛЕНИЕ ДЛЯ 24:00 ---
                    if end_str == "24:00":
                        # Интерпретируем 24:00 как конец текущего дня (23:59:59.999...)
                        # Для логики сравнения времени в пределах дня, используем 23:59:59
                        # или обрабатываем особым образом при вычислении end_datetime.
                        # Лучше сразу перейти к вычислению end_datetime.
                        is_end_midnight_next_day = True
                        # Для сравнения времени в пределах дня (current_time_only)
                        # end_time_for_comparison = time(23, 59, 59)
                        # Но для случая 23:00 - 24:00, current_time_only < 24:00 всегда True
                        # Поэтому логика активности для start <= current < end (где end=24:00)
                        # становится: start <= current_time_only (до конца дня)
                        # И время окончания - 00:00 следующего дня.
                    else:
                        end_time_for_comparison = datetime.strptime(end_str, '%H:%M').time()
                        is_end_midnight_next_day = False
                    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

                    # --- Вычисление активности ---
                    # Случай 1: start и end в один день (например, 01:00 - 02:00) или start и 24:00 (например, 23:00 - 24:00)
                    if start_time <= end_time_for_comparison or is_end_midnight_next_day:
                        # Для 24:00: start_time <= current_time_only (до конца дня)
                        # Для обычного: start_time <= current_time_only < end_time_for_comparison
                        if is_end_midnight_next_day:
                            # Событие активно, если start <= current_time_only и окно до конца дня
                            is_active = start_time <= current_time_only
                        else:
                            # Событие активно, если start <= current_time_only < end
                            is_active = start_time <= current_time_only < end_time_for_comparison

                        if is_active:
                            # Событие активно сегодня
                            # Вычисляем время окончания как datetime объект (на сегодня, в UTC)
                            # datetime.combine создает offset-naive datetime, нужно сделать его aware
                            # Для 24:00 - это конец текущего дня, т.е. 00:00 следующего дня
                            if is_end_midnight_next_day:
                                # Окончание в 24:00 означает 00:00 следующего дня
                                end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), datetime.min.time()) # time(0, 0)
                            else:
                                end_datetime_naive = datetime.combine(current_date_utc, end_time_for_comparison)
                            end_datetime = end_datetime_naive.replace(tzinfo=timezone.utc) # <-- offset-aware

                            # Проверяем, что end_datetime > current_time_utc, иначе добавляем день (маловероятно для 24:00, но на всякий)
                            if end_datetime <= current_time_utc:
                                logger.warning(f"End time {end_datetime} is <= current time {current_time_utc}, adding 1 day.")
                                if is_end_midnight_next_day:
                                     end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=2), datetime.min.time())
                                else:
                                     end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), end_time_for_comparison)
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
                            # --- ИСПРАВЛЕНИЕ: ЛОГИРОВАНИЕ ---
                            if is_end_midnight_next_day:
                                logger.info(f"Добавлено активное событие (окно до конца дня): {name} на {location}, осталось {time_left_str}")
                            else:
                                logger.info(f"Добавлено активное событие (сегодня): {name} на {location}, осталось {time_left_str}")
                            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
                            # Переходим к следующему окну, т.к. активное уже найдено для этого (name, location)
                            continue

                    # Случай 2: start > end (например, 23:00 - 01:00 -> событие пересекает полночь)
                    else: # start_time > end_time_for_comparison (и не 24:00)
                        if (current_time_only >= start_time) or (current_time_only < end_time_for_comparison):
                            # Событие активно сегодня или перешло на завтра
                            # Вычисляем время окончания
                            # Если текущее время >= start_time, значит событие началось сегодня и закончится завтра
                            if current_time_only >= start_time:
                                end_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), end_time_for_comparison)
                            else: # current_time_only < end_time_for_comparison -> событие началось вчера и заканчивается сегодня
                                end_datetime_naive = datetime.combine(current_date_utc, end_time_for_comparison)

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
                            # --- ИСПРАВЛЕНИЕ: ЛОГИРОВАНИЕ ---
                            # Было: logger.info(f"Добавлено активное событие (переходящее): {name} на {location}, осталось {time_left_str}")
                            # Стало:
                            if current_time_only < end_time_for_comparison:
                                 # Активно, потому что началось вчера
                                 log_msg_detail = f"началось вчера, закончится сегодня"
                            else:
                                 # Активно, потому что началось сегодня
                                 log_msg_detail = f"началось сегодня, закончится завтра"
                            logger.info(f"Добавлено активное событие (переходящее через полночь): {name} на {location} ({log_msg_detail}), осталось {time_left_str}")
                            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
                            continue # Переходим к следующему окну


                    # --- Вычисление предстоящего ---
                    # Если не активно, ищем ближайшее время начала
                    # Случай 1: start и end в один день (например, 01:00 - 02:00) или start и 24:00 (например, 23:00 - 24:00)
                    if start_time <= end_time_for_comparison or is_end_midnight_next_day:
                        if is_end_midnight_next_day:
                            # Если событие заканчивается в 24:00, оно начинается сегодня и заканчивается завтра.
                            # Если оно уже началось (start <= current), то оно активно (обработано выше).
                            # Если оно еще не началось (current < start), то начнётся сегодня.
                            if current_time_only < start_time: # Начнётся сегодня
                                start_datetime_naive = datetime.combine(current_date_utc, start_time)
                            else: # Уже началось, но активность не прошла (была бы выше), значит что-то не так с логикой или время на секунду изменилось.
                                 # На всякий случай, если current_time == start_time и оно не активно, ищем следующий день
                                 # Но это маловероятно, т.к. start <= current < 24:00 означает активность.
                                 # Если всё же не активно, ищем следующий день.
                                 start_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), start_time)
                        else:
                            if start_time > current_time_only: # Начнётся сегодня
                                start_datetime_naive = datetime.combine(current_date_utc, start_time)
                            else: # Началось сегодня, но уже прошло, ищем на завтра
                                start_datetime_naive = datetime.combine(current_date_utc + timedelta(days=1), start_time)

                    # Случай 2: start > end (например, 23:00 - 01:00)
                    else: # start_time > end_time_for_comparison
                        if current_time_only < start_time and current_time_only >= end_time_for_comparison: # Событие еще не началось сегодня (например, 22:00, а старт в 23:00)
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
                    # Пропускаем это окно, если ошибка парсинга (например, из-за 24:00 без обработки)
                    continue # Переходим к следующему окну
                except Exception as e:
                    logger.error(f"Unexpected error processing time for event {name} at {location}: {start_str}, {end_str}. Error: {e}")
                    continue # Переходим к следующему окну

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

        logger.info(f"Вычисление по API (events-schedule) завершено: {len(active_events)} активных, {len(upcoming_events)} предстоящих.")
        return active_events, upcoming_events

    except requests.RequestException as e:
        logger.error(f"Ошибка при получении данных из API (events-schedule): {e}")
        return [], []
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке данных из API (events-schedule): {e}")
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
        # ЗАМЕНИТЕ "https://t.me/your_telegram_username" НА РЕАЛЬНУЮ ССЫЛКУ
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
    # await callback_query.answer() # УБРАНО: edit_text или answer автоматически вызывают answer

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
    logger.info("Вызов send_events_message (использование API /events-schedule)")
    # МЕНЯЕМ: вызываем get_arc_raiders_events_from_api_schedule
    active, upcoming = get_arc_raiders_events_from_api_schedule()
    logger.info(f"Получено из API (events-schedule): {len(active)} активных, {len(upcoming)} предстоящих.")

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
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_events")], # Изменили callback
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
    logger.info("Обработка callback 'refresh_events' (использование API /events-schedule)") # <-- ДОБАВЛЕНО ЛОГИРОВАНИЕ
    await send_events_message(callback_query.message, edit=True)
    # await callback_query.answer() # УБРАНО: edit_text или answer автоматически вызывают answer

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
             return "" # или f"Нет предстоящих событий в ближайшее время.\n" если нужно сообщение

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
    logger.info("Запуск бота с использованием вычисленного таймера из API /events-schedule (все предстоящие), кнопками ссылок, текстом об обновлении и редактированием сообщений...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
