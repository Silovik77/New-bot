import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone, timedelta

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

# === ВАШИ ССЫЛКИ ===
STREAM_URL = "https://www.twitch.tv/silovik_"
CHANNEL_URL = "https://t.me/silovik_stream"
SUPPORT_URL = "https://dalink.to/silovik_"

# === ПЕРЕВОДЫ ===
EVENTS_RU = {
    "Lush Blooms": "Пышное Цветение",
    "Matriarch": "Матриарх",
    "Night Raid": "Ночной Налёт",
    "Uncovered Caches": "Обнаруженные Тайники",
    "Electromagnetic Storm": "Электромагнитная Буря",
    "Harvester": "Жнец",
    "Hidden Bunker": "Скрытый Бункер",
    "Husk Graveyard": "Кладбище Хасков",
    "Launch Tower Loot": "Добыча с Пусковой Башни",
    "Prospecting Probes": "Разведывательные Зонды",
}

MAPS_RU = {
    "Blue Gate": "Синие Врата",
    "Dam": "Плотина",
    "Spaceport": "Космопорт",
    "Buried City": "Погребённый Город",
    "Stella Montis": "Стелла Монтиc",
}


def tr_event(name): return EVENTS_RU.get(name, name)


def tr_map(name): return MAPS_RU.get(name, name)


# === ТОЧНОЕ РАСПИСАНИЕ (UTC) ИЗ САЙТА ===
EVENT_SCHEDULE = [
    # 9:00–10:00 UTC
    (9, "Harvester", ["Dam"]),
    (9, "Lush Blooms", ["Blue Gate"]),
    (9, "Night Raid", ["Buried City"]),
    (9, "Prospecting Probes", ["Spaceport"]),

    # 10:00–11:00 UTC
    (10, "Hidden Bunker", ["Spaceport"]),
    (10, "Husk Graveyard", ["Dam", "Buried City", "Blue Gate"]),
    (10, "Night Raid", ["Blue Gate"]),
    (10, "Prospecting Probes", ["Buried City"]),

    # 11:00–12:00 UTC
    (11, "Electromagnetic Storm", ["Dam", "Spaceport", "Blue Gate"]),
    (11, "Matriarch", ["Blue Gate"]),

    # 12:00–13:00 UTC
    (12, "Harvester", ["Spaceport"]),

    # 13:00–14:00 UTC
    (13, "Matriarch", ["Dam"]),

    # 14:00–15:00 UTC
    (14, "Night Raid", ["Spaceport"]),

    # 15:00–16:00 UTC
    (15, "Lush Blooms", ["Spaceport"]),

    # 16:00–17:00 UTC
    (16, "Uncovered Caches", ["Dam"]),
    (16, "Husk Graveyard", ["Blue Gate"]),

    # 17:00–18:00 UTC
    (17, "Electromagnetic Storm", ["Dam"]),
    (17, "Hidden Bunker", ["Blue Gate"]),

    # 18:00–19:00 UTC
    (18, "Night Raid", ["Blue Gate"]),
    (18, "Prospecting Probes", ["Spaceport"]),

    # 19:00–20:00 UTC
    (19, "Harvester", ["Blue Gate"]),
    (19, "Matriarch", ["Blue Gate"]),

    # 20:00–21:00 UTC
    (20, "Lush Blooms", ["Blue Gate"]),
    (20, "Matriarch", ["Dam"]),
    (20, "Night Raid", ["Dam", "Stella Montis"]),
    (20, "Uncovered Caches", ["Buried City"]),

    # 21:00–22:00 UTC
    (21, "Matriarch", ["Spaceport"]),
    (21, "Night Raid", ["Buried City"]),

    # 22:00–23:00 UTC
    (22, "Electromagnetic Storm", ["Blue Gate", "Dam", "Spaceport"]),

    # 23:00–00:00 UTC
    (23, "Prospecting Probes", ["Buried City", "Dam", "Blue Gate", "Spaceport"]),
]

# === ОБНОВЛЕНИЯ ИГРЫ ===
GAME_UPDATES = """
🎮 <b>ARC Raiders — Последние обновления</b>

🔖 <b>v1.2.5 (05.12.2025)</b>
• Исправлен баг с исчезающими ящиками в Плотине
• Уменьшен урон Жнеца на 15%
• Добавлена новая карта: Стелла Монтиc
• Оптимизация FPS на слабых ПК

🔗 <b>Официальные ресурсы</b>
• Сайт: https://arcreaiders.com  
• Discord: https://discord.gg/arc-raiders
"""


# === ВЫЧИСЛЕНИЕ СОБЫТИЙ ДЛЯ UTC+3 ===
def get_current_events():
    # Текущее время в UTC+3 (Москва)
    now_moscow = datetime.now(timezone(timedelta(hours=3)))
    # Конвертируем в UTC для сравнения с расписанием
    now_utc = now_moscow.astimezone(timezone.utc)

    current_hour = now_utc.hour
    minutes = now_utc.minute
    seconds = now_utc.second
    total_sec = minutes * 60 + seconds

    active = []
    upcoming = []

    # Все события из расписания
    for hour, event, maps in EVENT_SCHEDULE:
        start_time_sec = hour * 3600

        # Если событие идёт сейчас
        if start_time_sec <= total_sec < start_time_sec + 3600:
            time_left = start_time_sec + 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            for loc in maps:
                active.append({
                    'name': event,
                    'location': loc,
                    'info': f"Заканчивается через {int(mins)}m {int(secs)}s"
                })

        # Считаем время до следующего окна (включая завтра)
        else:
            if total_sec < start_time_sec:
                time_until = start_time_sec - total_sec
            else:
                time_until = (24 * 3600 - total_sec) + start_time_sec

            mins, secs = divmod(time_until, 60)
            for loc in maps:
                upcoming.append({
                    'name': event,
                    'location': loc,
                    'info': f"Начнётся через {int(mins)}m {int(secs)}s"
                })

    # Сортируем предстоящие по времени
    upcoming.sort(key=lambda x: int(x['info'].split()[2][:-1]) * 60 + int(x['info'].split()[3][:-1]))
    # Берём только ближайшие 10
    upcoming = upcoming[:10]

    return active, upcoming


# === TELEGRAM ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


@router.message(Command("start"))
async def start_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Все события", callback_data="events")
    kb.button(text="🆕 Обновления игры", callback_data="updates")
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события и новости", reply_markup=kb.as_markup())


@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    active, upcoming = get_current_events()
    parts = ["🎮 <b>ARC Raiders: События</b> (время в UTC+3)\n"]

    if active:
        parts.append("🟢 <b>Активные:</b>")
        for e in active:
            parts.append(f" • <b>{tr_event(e['name'])}</b> (<b>{tr_map(e['location'])}</b>) — {e['info']}")
    if upcoming:
        parts.append("\n⏳ <b>Предстоящие:</b>")
        for e in upcoming:
            parts.append(f" • <b>{tr_event(e['name'])}</b> (<b>{tr_map(e['location'])}</b>) — {e['info']}")

    msg = "\n".join(parts)
    if len(msg) > 4000:
        msg = msg[:3990] + "\n\n... (список усечён)"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="events")
    kb.button(text="🆕 Обновления", callback_data="updates")
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)

    current_text = callback.message.text or ""
    current_markup = callback.message.reply_markup
    new_markup = kb.as_markup()
    if current_text != msg or current_markup != new_markup:
        try:
            await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=new_markup)
        except:
            await callback.message.answer(msg, parse_mode="HTML", reply_markup=new_markup)
    else:
        await callback.answer("Данные не изменились.")


@router.callback_query(lambda c: c.data == "updates")
async def updates_handler(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="updates")
    kb.button(text="📅 Все события", callback_data="events")
    kb.button(text="⬅️ Назад", callback_data="start")
    kb.adjust(2)
    await callback.message.edit_text(GAME_UPDATES, parse_mode="HTML", reply_markup=kb.as_markup())


@router.callback_query(lambda c: c.data == "start")
async def back_to_start(callback: CallbackQuery):
    await start_handler(callback.message)


dp.include_router(router)


async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ ARC Raiders Telegram-бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())