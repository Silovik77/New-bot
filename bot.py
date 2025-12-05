import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
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

# === РАСПИСАНИЕ ИЗ EXCEL (время в Москве — UTC+3) ===
SCHEDULE = [
    # 0:00–1:00
    (0, "Matriarch", "Spaceport"),

    # 1:00–2:00
    (1, "Husk Graveyard", "Blue Gate"),

    # 2:00–3:00
    (2, "Prospecting Probes", "Buried City"),
    (2, "Electromagnetic Storm", "Dam"),
    (2, "Night Raid", "Stella Montis"),
    (2, "Uncovered Caches", "Dam"),

    # 3:00–4:00
    (3, "Matriarch", "Spaceport"),
    (3, "Matriarch", "Dam"),

    # 4:00–5:00
    (4, "Prospecting Probes", "Buried City"),

    # 5:00–6:00
    (5, "Lush Blooms", "Buried City"),
    (5, "Husk Graveyard", "Blue Gate"),
    (5, "Uncovered Caches", "Buried City"),

    # 6:00–7:00
    (6, "Launch Tower Loot", "Spaceport"),
    (6, "Matriarch", "Dam"),
    (6, "Matriarch", "Spaceport"),
    (6, "Lush Blooms", "Dam"),

    # 7:00–8:00
    (7, "Night Raid", "Buried City"),
    (7, "Prospecting Probes", "Spaceport"),

    # 8:00–9:00
    (8, "Electromagnetic Storm", "Blue Gate"),
    (8, "Harvester", "Dam"),
    (8, "Husk Graveyard", "Buried City"),

    # 9:00–10:00
    (9, "Launch Tower Loot", "Spaceport"),
    (9, "Night Raid", "Dam"),
    (9, "Prospecting Probes", "Dam"),
    (9, "Prospecting Probes", "Spaceport"),

    # 10:00–11:00
    (10, "Husk Graveyard", "Dam"),
    (10, "Night Raid", "Blue Gate"),
    (10, "Prospecting Probes", "Buried City"),

    # 11:00–12:00
    (11, "Electromagnetic Storm", "Blue Gate"),
    (11, "Electromagnetic Storm", "Dam"),
    (11, "Electromagnetic Storm", "Spaceport"),
    (11, "Prospecting Probes", "Blue Gate"),

    # 12:00–13:00
    (12, "Harvester", "Spaceport"),
    (12, "Prospecting Probes", "Spaceport"),

    # 13:00–14:00
    (13, "Lush Blooms", "Spaceport"),
    (13, "Husk Graveyard", "Dam"),

    # 14:00–15:00
    (14, "Uncovered Caches", "Dam"),

    # 15:00–16:00
    (15, "Lush Blooms", "Spaceport"),
    (15, "Night Raid", "Buried City"),

    # 16:00–17:00
    (16, "Uncovered Caches", "Dam"),
    (16, "Prospecting Probes", "Buried City"),
    (16, "Night Raid", "Spaceport"),

    # 17:00–18:00
    (17, "Husk Graveyard", "Buried City"),
    (17, "Electromagnetic Storm", "Dam"),
    (17, "Uncovered Caches", "Blue Gate"),
    (17, "Night Raid", "Dam"),
    (17, "Night Raid", "Stella Montis"),

    # 18:00–19:00
    (18, "Night Raid", "Blue Gate"),
    (18, "Uncovered Caches", "Spaceport"),
    (18, "Night Raid", "Buried City"),

    # 19:00–20:00
    (19, "Harvester", "Dam"),
    (19, "Electromagnetic Storm", "Spaceport"),
    (19, "Electromagnetic Storm", "Spaceport"),
    (19, "Electromagnetic Storm", "Blue Gate"),

    # 20:00–21:00
    (20, "Matriarch", "Blue Gate"),
    (20, "Night Raid", "Dam"),
    (20, "Lush Blooms", "Buried City"),

    # 21:00–22:00
    (21, "Prospecting Probes", "Buried City"),
    (21, "Husk Graveyard", "Blue Gate"),
    (21, "Harvester", "Spaceport"),

    # 22:00–23:00
    (22, "Electromagnetic Storm", "Spaceport"),
    (22, "Husk Graveyard", "Blue Gate"),

    # 23:00–0:00
    (23, "Prospecting Probes", "Dam"),
    (23, "Prospecting Probes", "Blue Gate"),
    (23, "Prospecting Probes", "Spaceport"),
    (23, "Matriarch", "Dam"),
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
    await message.answer("🎮 ARC Raiders: события (по расписанию из Excel)", reply_markup=kb.as_markup())

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
        except Exception:
            await callback.message.answer(msg, parse_mode="HTML", reply_markup=new_markup)
    else:
        await callback.answer("Данные не изменились.")

dp.include_router(router)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ ARC Raiders Telegram-бот запущен (по Excel-расписанию, Moscow Time)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())