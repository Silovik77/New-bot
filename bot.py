import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext  # <-- ВАЖНО: FSMContext импортирован
from aiogram.fsm.state import State, StatesGroup  # <-- ВАЖНО: StatesGroup импортирован
from aiogram.fsm.storage.memory import MemoryStorage

# --- Добавляем класс состояний для обратной связи ---
class Feedback(StatesGroup):
    waiting_for_message = State()

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

# Укажите ваш Telegram ID (число), чтобы получать сообщения. Найти можно, например, через @userinfobot
YOUR_TELEGRAM_ID = "348743068"

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
    "Cold Snap": "Заморозка",
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
    "streams": "https://www.twitch.tv/silovik_",
    "telegram": "https://t.me/silovik_stream", # Пример, замените на реальную ссылку
    "support": "https://dalink.to/silovik_", # Пример, замените на реальную ссылку
    # "update": "https://www.arcraiders.com/patch-notes", # Убрана, так как теперь текст
}

# --- Текст для обновления игры ---
# Впишите сюда текст, который будет отправляться при нажатии кнопки "Обновление игры"
GAME_UPDATE_TEXT = """
<strong>ИНФОРМАЦИЯ ОТ РАЗРАБОТЧИКОВ ARC RAIDERS!</strong> (11.12.2025)

🔉 <strong>Информация:</strong>
-Разработчики Arc Raiders запустили опрос о картах
 Его можно пройти тут:
https://id.embark.games/id/arc-raiders/survey

<strong>ОБНОВЛЕНИЕ ARC RAIDERS 1.6.0!</strong> (11.12.2025)
-Удален трос, позволявший игрокам выходить за пределы игровой зоны на Стелла Монтис.
-Исправлена ошибка столкновения, позволявшая игрокам перепрыгивать через стену и проваливаться сквозь неё в локации «Синие ворота».
-Исправлены ошибки в материалах, из-за которых некоторые объекты не блокировали пулевые выстрелы или дуговое зрение.
-Исправлена ошибка в системе столкновения на стартовой башне космопорта, из-за которой игроки могли быть сбиты сквозь стену.

Также разработчики сделали несколько заявлений:
-Теперь магазин косметики будет работать по вторникам, и в этот день будет происходить смена ассортимента.
-Во вторник выйдет крупное обновление, посвященное проблеме холода, которое также включает в себя множество других исправлений.
-В преддверии Рождества команда возьмет необходимый перерыв и вернется в январе, хотя в это время она по-прежнему будет отслеживать и решать важные проблемы.

<strong>КРУПНОЕ ОБНОВЛЕНИЕ 1.7.0 ARC RAIDERS!</strong> (16.12.2025)

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

-Беттина - (Скорость снижения прочности снижена с ~0,43 % до ~0,17 % за выстрел, на практике для полного исчерпания прочности требовалось около 12 полных магазинов, но теперь для этогонужно 26 (с учётом увеличенного размера магазина), размер базового магазина увеличен с 20 до 22, время перезарядки уменьшено с 5 до 4,5).
Эти изменения направлены на то, чтобы сделать Беттину менее зависимой от дополнительного оружия. Теперь это оружие должно быть более эффективным в PvP, но не слишком. Данные показывают, что это оружие по-прежнему является одним из самых эффективных в PvE при своей редкости. 

-Трещётка - (Размер базового магазина увеличен с 10 до 12).
Несмотря на то, что Rattler не предназначен для борьбы с Stitcher или Kettle на близком расстоянии, он получил небольшое улучшение, которое немного приближает его время до убийства в PvP на низких уровнях к показателям Stitcher и Kettle. Это оружие должно оставаться в своей роли более продуманного оружия, предполагающего, что игроки будут прятаться за укрытиями, стрелять контролируемыми очередями и следить за перезарядкой.

Другие изменение:

· Улучшено направленное звучание (позиционирование) врагов ARC.
· Увеличено количество одновременно воспроизводимых звуков шагов, повышен их приоритет.
· Исправлена ошибка, из-за которой шаги по металлическим лестницам становились слишком тихими при медленном движении.

· Электромагнитная буря: удары молнии теперь иногда оставляют после себя ценный предмет.

· Точка появления Матриарха на Дамбе перенесена в зону, которая лучше подчёркивает её сильные стороны.
· Добавлено условие карты «Locked Gate» для Синих ворот.
· Увеличена частота появления некоторых предметов и чертежей на Стелле Монтис.

· Навык «Не теряя импульс» теперь сильнее снижает расход выносливости.
· Навык «Расслабляющая прогулка»теперь действует во время движения в режиме прицеливания.

· Добавлена небольшая стоимость выносливости при входе в скольжение.
· Уменьшено ускорение при выполнении кувырка уклонения из скольжения.

· На ПК в настройках графики появился вариант «Как в кино» (для мощных систем).

· Добавлен новый ползунок для настройки интенсивности размытия в движении.

· Увеличена ценность лута в комнатах с эпическими ключами, чтобы они лучше соответствовала их редкости.
· Расширены точки появления чертежей для повышения их доступности в зонах, которые были недостаточно представлены.
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
                            logger.info(f"Добавлено активное событие (сегодня): {name} на {location}, осталось {time_left_str}")
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
                            logger.info(f"Добавлено активное событие (переходящее): {name} на {location}, осталось {time_left_str}")
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
        # ЗАМЕНИТЕ "https://t.me/your_telegram_username" НА РЕАЛЬНУЮ ССЫЛКУ
        [types.InlineKeyboardButton(text="Обратная связь", url="https://t.me/Silovik_ttv")],
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
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_menu")],
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

# --- НОВОЕ: Обработчики для обратной связи ---

@dp.callback_query(lambda c: c.data == 'feedback_start')
async def process_callback_feedback_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает сообщение пользователя для обратной связи."""
    await state.set_state(Feedback.waiting_for_message)
    await callback_query.message.answer("Пожалуйста, введите ваше сообщение для обратной связи:")
    await callback_query.answer()

@dp.message(Feedback.waiting_for_message)
async def process_feedback_message(message: types.Message, state: FSMContext):
    """Получает сообщение пользователя и отправляет его администратору."""
    user_message = message.text
    user = message.from_user

    # Формируем сообщение для отправки администратору
    admin_message = f"""
Новое сообщение в обратной связи от пользователя:

ID: {user.id}
Имя: {user.first_name} {user.last_name or ''}
Имя пользователя: @{user.username or 'не указано'}

Сообщение:
{user_message}
"""

    try:
        # Отправляем сообщение администратору (ваш ID)
        await bot.send_message(chat_id=YOUR_TELEGRAM_ID, text=admin_message, parse_mode='HTML')
        # Отправляем подтверждение пользователю
        await message.answer("Спасибо за ваше сообщение! Оно было отправлено.")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения администратору: {e}")
        await message.answer("Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.")

    # Сбрасываем состояние
    await state.clear()


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
        # <-- ИСПРАВЛЕНО: callback_data="refresh_events"
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_events")], # <-- Изменено с "events" на "refresh_events"
        # <-- ПРОВЕРКА: callback_data="start_menu"
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_menu")]
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
        [types.InlineKeyboardButton(text="📺 Стримы", url=LINKS["streams"])],
        [types.InlineKeyboardButton(text="💬 Телеграмм", url=LINKS["telegram"])],
        [types.InlineKeyboardButton(text="💸 Поддержка", url=LINKS["support"])],
        [types.InlineKeyboardButton(text="✉️ Обратная связь", callback_data="feedback_start")],
        [types.InlineKeyboardButton(text="🆕 Обновление игры", callback_data="game_update_text")]
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
