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

# === РАСПИСАНИЕ СОБЫТИЙ (в UTC, каждый день повторяется) ===
SCHEDULE = [
    # (час_начала, событие, карта)
    (20, "Harvester", "Dam"),
    (20, "Lush Blooms", "Blue Gate"),
    (20, "Night Raid", "Buried City"),
    (20, "Prospecting Probes", "Spaceport"),

    (21, "Husk Graveyard", "Dam"),
    (21, "Night Raid", "Blue Gate"),
    (21, "Prospecting Probes", "Buried City"),

    (22, "Electromagnetic Storm", "Blue Gate"),
    (22, "Electromagnetic Storm", "Dam"),
    (22, "Electromagnetic Storm", "Spaceport"),

    (23, "Prospecting Probes", "Buried City"),
    (23, "Prospecting Probes", "Dam"),
    (23, "Prospecting Probes", "Blue Gate"),
    (23, "Prospecting Probes", "Spaceport"),

    (0, "Harvester", "Spaceport"),
    (1, "Launch Tower Loot", "Spaceport"),
    (2, "Hidden Bunker", "Spaceport"),  # ← ВРЕМЕННО ОТКЛЮЧЁН
    (3, "Husk Graveyard", "Blue Gate"),
    (4, "Night Raid", "Spaceport"),
    (5, "Lush Blooms", "Buried City"),
    (6, "Matriarch", "Blue Gate"),
    (7, "Hidden Bunker", "Blue Gate"),  # ← ВРЕМЕННО ОТКЛЮЧЁН
    (8, "Night Raid", "Buried City"),
    (9, "Electromagnetic Storm", "Dam"),
    (10, "Harvester", "Blue Gate"),
    (11, "Matriarch", "Spaceport"),
    (12, "Launch Tower Loot", "Spaceport"),
    (13, "Husk Graveyard", "Dam"),
    (14, "Night Raid", "Blue Gate"),
    (15, "Prospecting Probes", "Spaceport"),
    (16, "Matriarch", "Dam"),
    (17, "Electromagnetic Storm", "Spaceport"),
    (18, "Harvester", "Dam"),
    (19, "Lush Blooms", "Spaceport"),
]

def get_current_events():
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_sec = minutes * 60 + seconds

    active = []
    upcoming = []

    # === АКТИВНЫЕ СОБЫТИЯ ===
    for hour, event, loc in SCHEDULE:
        if hour == current_hour and total_sec < 3600:
            time_left = 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            if event != "Hidden Bunker":  # Исключаем
                active.append({
                    'name': event,
                    'location': loc,
                    'info': f"Заканчивается через {int(mins)}m {int(secs)}s"
                })

    # === ПРЕДСТОЯЩИЕ СОБЫТИЯ ===
    next_hour = (current_hour + 1) % 24
    for hour, event, loc in SCHEDULE:
        if hour == next_hour:
            time_until = 3600 - total_sec
            mins, secs = divmod(time_until, 60)
            if event != "Hidden Bunker":  # Исключаем
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
    kb.button(text="📅 События", callback_data="events")
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события по картам", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    active, upcoming = get_current_events()
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
    print("✅ ARC Raiders Telegram-бот запущен (статичный таймер)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())