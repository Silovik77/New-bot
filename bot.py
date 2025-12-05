import asyncio
import logging
import os
import requests
import re
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

# === ПАРСИНГ С САЙТА ARCRaidersHub ===
def fetch_events_from_hub():
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Telegram Bot)"}
    resp = requests.get("https://arcraidershub.com/events", headers=headers, timeout=10)
    resp.raise_for_status()
    html = resp.text

    # Извлекаем события из HTML
    events = []
    # Пример: <span class="event-name">Harvester</span> <span class="event-map">Dam</span> <span class="event-time">19:00–20:00</span>
    pattern = r'<span class="event-name">([^<]+)</span>.*?<span class="event-map">([^<]+)</span>.*?<span class="event-time">(\d{2}):\d{2}–(\d{2}):\d{2}</span>'
    matches = re.findall(pattern, html, re.DOTALL)

    for name, loc, start_h, end_h in matches:
        start_hour = int(start_h)
        end_hour = int(end_h)
        # Добавляем каждое событие на каждый час, в который оно идёт
        for hour in range(start_hour, end_hour):
            events.append({
                'name': name.strip(),
                'location': loc.strip(),
                'start_hour': hour,
                'end_hour': (hour + 1) % 24
            })

    return events

def get_current_events():
    # Московское время (UTC+3)
    now = datetime.now(timezone(timedelta(hours=3)))
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_sec = minutes * 60 + seconds

    events = fetch_events_from_hub()
    active = []
    upcoming = []

    # === АКТИВНЫЕ СОБЫТИЯ ===
    for ev in events:
        if ev['start_hour'] == current_hour and total_sec < 3600:
            time_left = 3600 - total_sec
            mins, secs = divmod(time_left, 60)
            active.append({
                'name': ev['name'],
                'location': ev['location'],
                'info': f"Заканчивается через {int(mins)}m {int(secs)}s",
                'time': f"({ev['start_hour']}:00–{ev['end_hour']}:00 МСК)"
            })

    # === ПРЕДСТОЯЩИЕ СОБЫТИЯ ===
    next_hour = (current_hour + 1) % 24
    for ev in events:
        if ev['start_hour'] == next_hour:
            time_until = 3600 - total_sec
            mins, secs = divmod(time_until, 60)
            upcoming.append({
                'name': ev['name'],
                'location': ev['location'],
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
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события (по расписанию с arcraidershub.com)", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    await callback.answer()
    try:
        active, upcoming = get_current_events()
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
        return

    if not active and not upcoming:
        msg = " august Нет событий."
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
    print("✅ ARC Raiders Telegram-бот запущен (из arcraidershub.com)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())