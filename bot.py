import asyncio
import logging
import os
import re
import requests
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

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


# === ПОЛУЧЕНИЕ СОБЫТИЙ ИЗ САЙТА (ТОЛЬКО Active now + Upcoming next) ===
def get_events_from_site():
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get("https://metaforge.app/arc-raiders/event-timers", headers=headers, timeout=10)
    resp.raise_for_status()
    html = resp.text

    active = []
    upcoming = []

    # --- Парсинг Active now ---
    active_match = re.search(r'Active now\s*(.*?)\s*Upcoming next', html, re.DOTALL)
    if active_match:
        block = active_match.group(1)
        for line in block.splitlines():
            if "Ends in" in line:
                parts = line.split(" Ends in ", 1)
                if len(parts) == 2:
                    name_loc = parts[0].strip()
                    time_left = parts[1].strip()
                    # Пропускаем "Hidden Bunker"
                    if "Hidden Bunker" in name_loc:
                        continue
                    for ev in EVENTS_RU:
                        if name_loc.startswith(ev):
                            loc = name_loc[len(ev):].strip()
                            if loc:
                                active.append({
                                    'name': ev,
                                    'location': loc,
                                    'info': f"Заканчивается через {time_left}"
                                })
                            break

    # --- Парсинг Upcoming next ---
    upcoming_match = re.search(r'Upcoming next\s*(.*?)(?:####|\Z)', html, re.DOTALL)
    if upcoming_match:
        block = upcoming_match.group(1)
        for line in block.splitlines():
            if "Starts in" in line:
                parts = line.split(" Starts in ", 1)
                if len(parts) == 2:
                    name_loc = parts[0].strip()
                    time_left = parts[1].strip()
                    # Пропускаем "Hidden Bunker"
                    if "Hidden Bunker" in name_loc:
                        continue
                    for ev in EVENTS_RU:
                        if name_loc.startswith(ev):
                            loc = name_loc[len(ev):].strip()
                            if loc:
                                upcoming.append({
                                    'name': ev,
                                    'location': loc,
                                    'info': f"Начнётся через {time_left}"
                                })
                            break

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
    try:
        active, upcoming = get_events_from_site()
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка загрузки: {e}")
        return

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