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

STREAM_URL = "https://www.twitch.tv/silovik_"
CHANNEL_URL = "https://t.me/silovik_stream"
SUPPORT_URL = "https://dalink.to/silovik_"

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


# === ФУНКЦИЯ: ВЫЧИСЛЕНИЕ СОБЫТИЙ НА ОСНОВЕ ТЕКУЩЕГО ВРЕМЕНИ (UTC) ===
def get_current_events():
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_sec = minutes * 60 + seconds

    active = []
    upcoming = []

    # === АКТИВНЫЕ СОБЫТИЯ (8:00–9:00 UTC) ===
    if current_hour == 8 and total_sec < 3600:
        time_left = 3600 - total_sec
        mins, secs = divmod(time_left, 60)
        active.extend([
            {"name": "Lush Blooms", "location": "Blue Gate", "info": f"Заканчивается через {mins}m {secs}s"},
            {"name": "Matriarch", "location": "Dam", "info": f"Заканчивается через {mins}m {secs}s"},
            {"name": "Night Raid", "location": "Dam", "info": f"Заканчивается через {mins}m {secs}s"},
            {"name": "Night Raid", "location": "Stella Montis", "info": f"Заканчивается через {mins}m {secs}s"},
            {"name": "Uncovered Caches", "location": "Buried City", "info": f"Заканчивается через {mins}m {secs}s"},
        ])

    # === ПРЕДСТОЯЩИЕ СОБЫТИЯ (9:00–10:00 UTC) ===
    if current_hour == 9 and total_sec < 3600:
        time_left = 3600 - total_sec
        mins, secs = divmod(time_left, 60)
        upcoming.extend([
            {"name": "Matriarch", "location": "Spaceport", "info": f"Заканчивается через {mins}m {secs}s"},
            {"name": "Night Raid", "location": "Buried City", "info": f"Заканчивается через {mins}m {secs}s"},
        ])
    elif current_hour == 8:  # если сейчас 8:xx, то следующие события — в 9:00
        time_until = 3600 - total_sec
        mins, secs = divmod(time_until, 60)
        upcoming.extend([
            {"name": "Matriarch", "location": "Spaceport", "info": f"Начнётся через {mins}m {secs}s"},
            {"name": "Night Raid", "location": "Buried City", "info": f"Начнётся через {mins}m {secs}s"},
        ])

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