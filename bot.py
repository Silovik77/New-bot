import asyncio
import logging
import os
import subprocess
import sys
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from playwright.async_api import async_playwright

# === УСТАНОВКА PLAYWRIGHT ===
def install_playwright():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Chromium установлен")
    except Exception as e:
        print(f"❌ Ошибка установки Chromium: {e}")
        raise

install_playwright()

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

URL = "https://metaforge.app/arc-raiders/event-timers"

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

# === ПАРСИНГ СОБЫТИЙ ===
async def fetch_events():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle", timeout=30000)

        # Ждём появления карточек событий
        await page.wait_for_selector("div.flex.items-center.justify-between.p-2", timeout=20000)

        events = []
        # Извлекаем текст
        text = await page.text_content("body")
        await browser.close()

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Активные
        try:
            i_active = lines.index("Active now")
            i_upcoming = lines.index("Upcoming next")
        except ValueError:
            i_active = -1
            i_upcoming = len(lines)

        if i_active != -1:
            i = i_active + 1
            while i < i_upcoming:
                line = lines[i]
                if line.startswith("!") or not line:
                    i += 1
                    continue
                if "Ends in" in line:
                    parts = line.split(" Ends in ", 1)
                    if len(parts) == 2:
                        name_loc = parts[0].strip()
                        time_left = parts[1].strip()
                        for ev in sorted(EVENTS_RU.keys(), key=len, reverse=True):
                            if name_loc.startswith(ev):
                                loc = name_loc[len(ev):].strip()
                                events.append({
                                    'name': ev,
                                    'location': loc,
                                    'info': f"Заканчивается через {time_left}",
                                    'type': 'active'
                                })
                                break
                i += 1

        # Предстоящие
        i = i_upcoming + 1
        while i < len(lines):
            line = lines[i]
            if line.startswith("####"):
                break
            if line.startswith("!") or not line:
                i += 1
                continue
            if "Starts in" in line:
                parts = line.split(" Starts in ", 1)
                if len(parts) == 2:
                    name_loc = parts[0].strip()
                    time_left = parts[1].strip()
                    for ev in sorted(EVENTS_RU.keys(), key=len, reverse=True):
                        if name_loc.startswith(ev):
                            loc = name_loc[len(ev):].strip()
                            # Исключаем Hidden Bunker
                            if ev == "Hidden Bunker":
                                i += 1
                                continue
                            events.append({
                                'name': ev,
                                'location': loc,
                                'info': f"Начнётся через {time_left}",
                                'type': 'upcoming'
                            })
                            break
            i += 1

    return events, []

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
    await callback.answer()
    try:
        active, upcoming = await fetch_events()
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
        return

    if not active and not upcoming:
        msg = " أغسطس Нет событий."
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
    print("✅ ARC Raiders Telegram-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())