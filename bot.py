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

# === ССЫЛКИ ===
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
    # 8:00–9:00 UTC — АКТИВНЫЕ СЕЙЧАС
    (8, "Harvester", ["Dam"]),
    (8, "Lush Blooms", ["Blue Gate"]),
    (8, "Night Raid", ["Buried City"]),
    (8, "Prospecting Probes", ["Spaceport"]),

    # 9:00–10:00 UTC — ПРЕДСТОЯЩИЕ
    (9, "Hidden Bunker", ["Spaceport"]),
    (9, "Husk Graveyard", ["Dam", "Buried City", "Blue Gate"]),
    (9, "Night Raid", ["Blue Gate"]),
    (9, "Prospecting Probes", ["Buried City"]),

    # 10:00–11:00 UTC
    (10, "Electromagnetic Storm", ["Dam", "Spaceport", "Blue Gate"]),
    (10, "Matriarch", ["Blue Gate"]),

    # 11:00–12:00 UTC
    (11, "Harvester", ["Spaceport"]),
    (12, "Matriarch", ["Dam"]),
    (13, "Night Raid", ["Spaceport"]),
    (14, "Lush Blooms", ["Spaceport"]),
    (15, "Uncovered Caches", ["Dam"]),
    (15, "Husk Graveyard", ["Blue Gate"]),
    (16, "Electromagnetic Storm", ["Dam"]),
    # (17, "Hidden Bunker", ["Blue Gate"]),  # ← ВРЕМЕННО УДАЛЁН
    (18, "Night Raid", ["Blue Gate"]),
    (18, "Prospecting Probes", ["Spaceport"]),
    (19, "Harvester", ["Blue Gate"]),
    (19, "Matriarch", ["Blue Gate"]),
    (20, "Lush Blooms", ["Blue Gate"]),
    (20, "Matriarch", ["Dam"]),
    (20, "Night Raid", ["Dam", "Stella Montis"]),
    (20, "Uncovered Caches", ["Buried City"]),
    (21, "Matriarch", ["Spaceport"]),
    (21, "Night Raid", ["Buried City"]),
    (22, "Electromagnetic Storm", ["Blue Gate", "Dam", "Spaceport"]),
    (23, "Prospecting Probes", ["Buried City", "Dam", "Blue Gate", "Spaceport"]),
]


# === ВЫЧИСЛЕНИЕ СОБЫТИЙ (в UTC) ===
def get_current_events():
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    total_sec = now.minute * 60 + now.second

    # Список событий из "Active now" и "Upcoming next"
    events = [
        # === АКТИВНЫЕ СЕЙЧАС (8:00–9:00 UTC) ===
        {"hour": 8, "name": "Lush Blooms", "location": "Blue Gate", "status": "active"},
        {"hour": 8, "name": "Matriarch", "location": "Dam", "status": "active"},
        {"hour": 8, "name": "Night Raid", "location": "Dam", "status": "active"},
        {"hour": 8, "name": "Night Raid", "location": "Stella Montis", "status": "active"},
        {"hour": 8, "name": "Uncovered Caches", "location": "Buried City", "status": "active"},

        # === ПРЕДСТОЯЩИЕ (9:00–10:00 UTC) ===
        {"hour": 9, "name": "Matriarch", "location": "Spaceport", "status": "upcoming"},
        {"hour": 9, "name": "Night Raid", "location": "Buried City", "status": "upcoming"},

        # === ОСТАЛЬНЫЕ СОБЫТИЯ В ЦИКЛЕ (из блоков ниже) ===
        {"hour": 10, "name": "Husk Graveyard", "location": "Dam", "status": "upcoming"},
        {"hour": 10, "name": "Husk Graveyard", "location": "Buried City", "status": "upcoming"},
        {"hour": 10, "name": "Husk Graveyard", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 10, "name": "Night Raid", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 10, "name": "Prospecting Probes", "location": "Buried City", "status": "upcoming"},

        {"hour": 11, "name": "Electromagnetic Storm", "location": "Dam", "status": "upcoming"},
        {"hour": 11, "name": "Electromagnetic Storm", "location": "Spaceport", "status": "upcoming"},
        {"hour": 11, "name": "Electromagnetic Storm", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 11, "name": "Matriarch", "location": "Blue Gate", "status": "upcoming"},

        {"hour": 12, "name": "Harvester", "location": "Spaceport", "status": "upcoming"},

        {"hour": 13, "name": "Matriarch", "location": "Dam", "status": "upcoming"},

        {"hour": 14, "name": "Night Raid", "location": "Spaceport", "status": "upcoming"},

        {"hour": 15, "name": "Lush Blooms", "location": "Spaceport", "status": "upcoming"},

        {"hour": 16, "name": "Uncovered Caches", "location": "Dam", "status": "upcoming"},
        {"hour": 16, "name": "Husk Graveyard", "location": "Blue Gate", "status": "upcoming"},

        {"hour": 17, "name": "Electromagnetic Storm", "location": "Dam", "status": "upcoming"},

        {"hour": 18, "name": "Night Raid", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 18, "name": "Prospecting Probes", "location": "Spaceport", "status": "upcoming"},

        {"hour": 19, "name": "Harvester", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 19, "name": "Matriarch", "location": "Blue Gate", "status": "upcoming"},

        {"hour": 20, "name": "Lush Blooms", "location": "Blue Gate", "status": "active"},
        {"hour": 20, "name": "Matriarch", "location": "Dam", "status": "active"},
        {"hour": 20, "name": "Night Raid", "location": "Dam", "status": "active"},
        {"hour": 20, "name": "Night Raid", "location": "Stella Montis", "status": "active"},
        {"hour": 20, "name": "Uncovered Caches", "location": "Buried City", "status": "active"},

        {"hour": 21, "name": "Matriarch", "location": "Spaceport", "status": "upcoming"},
        {"hour": 21, "name": "Night Raid", "location": "Buried City", "status": "upcoming"},

        {"hour": 22, "name": "Electromagnetic Storm", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 22, "name": "Electromagnetic Storm", "location": "Dam", "status": "upcoming"},
        {"hour": 22, "name": "Electromagnetic Storm", "location": "Spaceport", "status": "upcoming"},

        {"hour": 23, "name": "Prospecting Probes", "location": "Buried City", "status": "upcoming"},
        {"hour": 23, "name": "Prospecting Probes", "location": "Dam", "status": "upcoming"},
        {"hour": 23, "name": "Prospecting Probes", "location": "Blue Gate", "status": "upcoming"},
        {"hour": 23, "name": "Prospecting Probes", "location": "Spaceport", "status": "upcoming"},
    ]

    # Удаляем "Hidden Bunker" — даже если он попал сюда
    events = [e for e in events if e["name"] != "Hidden Bunker"]

    active = []
    upcoming = []

    for e in events:
        if e["hour"] == current_hour and total_sec < 3600 and e["status"] == "active":
            time_left = 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            active.append({
                'name': e['name'],
                'location': e['location'],
                'info': f"Заканчивается через {int(mins)}m {int(secs)}s"
            })
        elif e["hour"] == (current_hour + 1) % 24 and e["status"] == "upcoming":
            time_until = 3600 - total_sec
            mins, secs = divmod(time_until, 60)
            upcoming.append({
                'name': e['name'],
                'location': e['location'],
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
    await message.answer("🎮 ARC Raiders: события и новости", reply_markup=kb.as_markup())


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
        for e in upcoming[:10]:
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
    print("✅ ARC Raiders Telegram-бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())