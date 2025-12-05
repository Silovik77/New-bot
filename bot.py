import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

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

# === РАСПИСАНИЕ (время в Москве — UTC+3) ===
SCHEDULE = [
    # (час_начала_мск, событие, карта)




    (0, "Matriarch", "Dam"),
    (0, "Matriarch", "Spaceport"),

    (1, "Electromagnetic Storm", "Blue Gate"),
    (1,"Night Raid", "Stella Montis"),
    (1,"Night Raid", "Spaceport"),

    (2, "Prospecting Probes", "Buried City"),
    (2,  "Buried City", "Dam"),
    (2, "Night Raid", "Stella Montis"),
    (2, "Electromagnetic Storm", "Dam"),

    (3, "Matriarch", "Dam"),
    (3, "Night Raid", "Buried City"),
    (3, "Harvester", "Spaceport"),

    (4, "Night Raid", "Spaceport"),

    (5, "Night Raid", "Dam"),
    (5, "Uncovered Caches", "Buried City"),
    (5, "Husk Graveyard", "Blue Gate"),


    (6, "Lush Blooms", "Dam"),
    (6, "Night Raid", "Buried City"),
    (6, "Matriarch", "Spaceport"),

    (7, "Electromagnetic Storm", "Spaceport"),
    (7, "Night Raid", "Blue Gate"),

    (8, "Electromagnetic Storm", "Dam"),
    (8, "Husk Graveyard", "Buried City"),
    (8, "Harvester", "Blue Gate"),

    (9, "Launch Tower Loot", "Spaceport"),
    (9, "Prospecting Probes", "Dam"),
    (9, "Night Raid", "Buried City"),

    (10, "Electromagnetic Storm", "Blue Gate"),
    (10, "Night Raid", "Spaceport"),

    (11, "Night Raid", "Dam"),
    (11, "Lush Blooms", "Buried City"),
    (11, "Prospecting Probes", "Blue Gate"),

    (12, "Harvester", "Dam"),
    (12, "Night Raid", "Buried City"),
    (12, "Prospecting Probes", "Spaceport"),
    (12, "Lush Blooms", "Blue Gate"),

    (13, "Husk Graveyard", "Dam"),
    (13, "Hidden Bunker", "Spaceport"),
    (13, "Night Raid", "Blue Gate"),

    (14, "Electromagnetic Storm", "Dam"),
    (14, "Prospecting Probes", "Buried City"),
    (14, "Matriarch", "Blue Gate"),

    (15, "Lush Blooms", "Spaceport"),
    (15, "Night Raid", "Buried City"),

    (16, "Prospecting Probes", "Dam"),
    (16, "Night Raid", "Spaceport"),

    (17, "Night Raid", "Dam"),
    (17, "Husk Graveyard", "Buried City"),
    (17, "Uncovered Caches", "Blue Gate"),

    (18, "Uncovered Caches", "Spaceport"),

    (19, "Harvester", "Dam"),
    (19, "Electromagnetic Storm", "Spaceport"),
    (19, "Electromagnetic Storm", "Blue Gate"),

    (20, "Harvester", "Blue Gate"),
    (20, "Electromagnetic Storm", "Dam"),
    (20, "Lush Blooms", "Dam"),
    (20, "Lush Blooms", "Buried City"),
    (20, "Night Raid", "Stella Montis"),

    (21, "Night Raid", "Buried City"),
    (21, "Harvester", "Spaceport"),
    (21, "Husk Graveyard", "Blue Gate"),

    (22, "Hidden Bunker", "Spaceport"),
    (22, "Night Raid", "Blue Gate"),


    (21, "Prospecting Probes", "Buried City"),

    (22, "Husk Graveyard", "Blue Gate"),

    (23, "Matriarch", "Dam"),
    (23, "Uncovered Caches", "Buried City"),
    (23, "Lush Blooms", "Blue Gate"),

]

def get_current_events():
    # Московское время (UTC+3)
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_sec = minutes * 60 + seconds

    active = []
    upcoming = []

    # === АКТИВНЫЕ СОБЫТИЯ (в этом часу по Москве) ===
    for hour, event, loc in SCHEDULE:
        if hour == current_hour and total_sec < 3600:
            time_left = 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            active.append({
                'name': event,
                'location': loc,
                'info': f"Заканчивается через {int(mins)}m {int(secs)}s",
                'time': f"({hour}:00–{hour + 1}:00 МСК)"
            })

    # === ПРЕДСТОЯЩИЕ СОБЫТИЯ (в следующем часу по Москве) ===
    next_hour = (current_hour + 1) % 24
    for hour, event, loc in SCHEDULE:
        if hour == next_hour:
            time_until = 3600 - total_sec
            mins, secs = divmod(time_until, 60)
            upcoming.append({
                'name': event,
                'location': loc,
                'info': f"Начнётся через {int(mins)}m {int(secs)}s",
                'time': f"({next_hour}:00–{next_hour + 1}:00 МСК)"
            })

    return active, upcoming

# === TELEGRAM ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 События", callback_data="events")
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события (по расписанию из hub.arcraiders.com)", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    await callback.answer()
    active, upcoming = get_current_events()

    if not active and not upcoming:
        msg = " agosto Нет событий."
    else:
        parts = ["🎮 <b>ARC Raiders: События</b> (время в Москве, UTC+3)\n"]
        if active:
            parts.append("🟢 <b>Сейчас:</b>")
            for e in active:
                parts.append(f" • <b>{tr_event(e['name'])}</b> ({tr_map(e['location'])}) — {e['info']} {e['time']}")
        if upcoming:
            parts.append("\n⏳ <b>Скоро:</b>")
            for e in upcoming[:30]:
                parts.append(f" • <b>{tr_event(e['name'])}</b> ({tr_map(e['location'])}) — {e['info']} {e['time']}")

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
    print("✅ ARC Raiders Telegram-бот запущен (по расписанию из Excel, Moscow Time)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())