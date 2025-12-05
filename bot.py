import asyncio
import logging
import os
from datetime import datetime, timezone
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

# === ПОЛНОЕ РАСПИСАНИЕ (из Excel + HTML) ===
SCHEDULE = [
    # 0:00–1:00 UTC
    (0, "Matriarch", "Spaceport"),


    # 1:00–2:00 UTC
    (1, "Electromagnetic Storm", "Blue Gate"),

    # 2:00–3:00 UTC
    (2, "Uncovered Caches", "Dam"),
    (2, "Matriarch", "Blue Gate"),
    (2, "Electromagnetic Storm", "Dam"),
    (2, "Prospecting Probes", "Buried City"),

    # 3:00–4:00 UTC
    (3, "Matriarch", "Dam"),
(3, "Harvester", "Spaceport"),


    # 5:00–6:00 UTC
    (5, "Lush Blooms", "Buried City"),

    # 6:00–7:00 UTC
    (6, "Matriarch", "Blue Gate"),
    (6, "Electromagnetic Storm", "Spaceport"),

    # 7:00–8:00 UTC
    (7, "Night Raid", "Buried City"),

    # 8:00–9:00 UTC
    (8, "Electromagnetic Storm", "Blue Gate"),
    (8, "Harvester", "Dam"),

    # 9:00–10:00 UTC
    (9, "Launch Tower Loot", "Spaceport"),
    (9, "Night Raid", "Dam"),

    # 10:00–11:00 UTC
    (10, "Husk Graveyard", "Dam"),
    (10, "Husk Graveyard", "Buried City"),
    (10, "Husk Graveyard", "Blue Gate"),

    # 11:00–12:00 UTC
    (11, "Electromagnetic Storm", "Blue Gate"),
    (11, "Electromagnetic Storm", "Dam"),
    (11, "Electromagnetic Storm", "Spaceport"),

    # 12:00–13:00 UTC
    (12, "Harvester", "Spaceport"),
    (12, "Prospecting Probes", "Spaceport"),

    # 13:00–14:00 UTC
    (13, "Lush Blooms", "Spaceport"),

    # 14:00–15:00 UTC
    (14, "Uncovered Caches", "Dam"),

    # 15:00–16:00 UTC
    (15, "Lush Blooms", "Spaceport"),
    (15, "Night Raid", "Buried City"),

    # 16:00–17:00 UTC
    (16, "Night Raid", "Spaceport"),
    (16, "Prospecting Probes", "Dam"),


    # 17:00–18:00 UTC
    (17, "Husk Graveyard", "Buried City"),
    (17, "Electromagnetic Storm", "Dam"),

    # 18:00–19:00 UTC
    (18, "Night Raid", "Blue Gate"),
    (18, "Prospecting Probes", "Spaceport"),

    # 19:00–20:00 UTC
    (19, "Harvester", "Dam"),
    (19, "Electromagnetic Storm", "Spaceport"),

    # 20:00–21:00 UTC
    (20, "Matriarch", "Blue Gate"),
    (20, "Night Raid", "Dam"),
    (20, "Lush Blooms", "Blue Gate"),

    # 21:00–22:00 UTC
    (21, "Matriarch", "Spaceport"),
    (21, "Prospecting Probes", "Buried City"),

    # 22:00–23:00 UTC
    (22, "Husk Graveyard", "Blue Gate"),

    # 23:00–0:00 UTC
    (23, "Prospecting Probes", "Dam"),
    (23, "Prospecting Probes", "Blue Gate"),
    (23, "Prospecting Probes", "Spaceport"),
]

def get_current_events():
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_sec = minutes * 60 + seconds

    active = []
    upcoming = []

    # === АКТИВНЫЕ СОБЫТИЯ (в этом часу) ===
    for hour, event, loc in SCHEDULE:
        if hour == current_hour and total_sec < 3600:
            time_left = 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            active.append({
                'name': event,
                'location': loc,
                'info': f"Заканчивается через {int(mins)}m {int(secs)}s",
                'type': 'active'
            })

    # === ПРЕДСТОЯЩИЕ СОБЫТИЯ (в следующем часу) ===
    next_hour = (current_hour + 1) % 24
    for hour, event, loc in SCHEDULE:
        if hour == next_hour:
            time_until = 3600 - total_sec
            mins, secs = divmod(time_until, 60)
            upcoming.append({
                'name': event,
                'location': loc,
                'info': f"Начнётся через {int(mins)}m {int(secs)}s",
                'type': 'upcoming'
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
    await message.answer("🎮 ARC Raiders: события по расписанию", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    await callback.answer()
    try:
        active, upcoming = get_current_events()
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
        return

    if not active and not upcoming:
        msg = " agosto Нет событий."
    else:
        parts = ["🎮 <b>ARC Raiders: События</b> (время в UTC)\n"]
        if active:
            parts.append("🟢 <b>Сейчас:</b>")
            for e in active:
                parts.append(f" • <b>{tr_event(e['name'])}</b> ({tr_map(e['location'])}) — {e['info']}")
        if upcoming:
            parts.append("\n⏳ <b>Скоро:</b>")
            for e in upcoming[:30]:
                parts.append(f" • <b>{tr_event(e['name'])}</b> ({tr_map(e['location'])}) — {e['info']}")

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
    print("✅ ARC Raiders Telegram-бот запущен (по расписанию из Excel)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())