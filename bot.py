import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone

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


# === ТОЧНОЕ РАСПИСАНИЕ (UTC) ИЗ ОФИЦИАЛЬНОГО ИСТОЧНИКА ===
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


# === ВЫЧИСЛЕНИЕ СОБЫТИЙ ===
def get_current_events():
    # Получаем текущее время в UTC+3 (Москва)
    now_moscow = datetime.now(timezone(timedelta(hours=3)))
    # Конвертируем в UTC для сравнения с расписанием
    now_utc = now_moscow.astimezone(timezone.utc)

    current_hour = now_utc.hour
    minutes = now_utc.minute
    seconds = now_utc.second
    total_sec = minutes * 60 + seconds

    active = []
    upcoming = []

    # Текущие события (в этом часу по UTC)
    for hour, event, maps in EVENT_SCHEDULE:
        if hour == current_hour and total_sec < 3600:
            time_left = 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            for loc in maps:
                active.append({
                    'name': event,
                    'location': loc,
                    'info': f"Заканчивается через {int(mins)}m {int(secs)}s"
                })

    # Следующие события (в следующем часу по UTC)
    next_hour = (current_hour + 1) % 24
    for hour, event, maps in EVENT_SCHEDULE:
        if hour == next_hour:
            time_until = 3600 - total_sec
            mins, secs = divmod(time_until, 60)
            for loc in maps:
                upcoming.append({
                    'name': event,
                    'location': loc,
                    'info': f"Начнётся через {int(mins)}m {int(secs)}s"
                })

    return active, upcoming


# === TELEGRAM ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()


@router.message(Command("start"))
async def start_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Все события", callback_data="events")
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: текущие и предстоящие события", reply_markup=kb.as_markup())


@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    active, upcoming = get_current_events()
    parts = ["🎮 <b>ARC Raiders: События</b> (время в UTC)\n"]

    if active:
        parts.append("🟢 <b>Активные:</b>")
        for e in active:
            parts.append(f" • <b>{tr_event(e['name'])}</b> (<b>{tr_map(e['location'])}</b>) — {e['info']}")
    if upcoming:
        parts.append("\n⏳ <b>Предстоящие:</b>")
        for e in upcoming[:20]:
            parts.append(f" • <b>{tr_event(e['name'])}</b> (<b>{tr_map(e['location'])}</b>) — {e['info']}")

    msg = "\n".join(parts)
    if len(msg) > 4000:
        msg = msg[:3990] + "\n\n... (список усечён)"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="events")
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)

    # Обход ошибки "message is not modified"
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


dp.include_router(router)


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())