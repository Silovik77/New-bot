import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

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

# === ОБНОВЛЕНИЯ ИГРЫ ===
GAME_UPDATES = """
🎮 <b>ARC Raiders — Последние обновления</b>

🔖 <b>v1.2.5 (04.12.2025)</b>
• Исправлен баг с исчезающими ящиками в Плотине
• Уменьшен урон Жнеца на 15%
• Добавлена новая карта: Стелла Монтиc (на пробе)
• Оптимизация FPS на слабых ПК

🔖 <b>v1.2.4 (28.11.2025)</b>
• Исправлен вылет при входе в подземелья
• Снижена длительность Ночного Налёта с 2ч до 1ч
• Исправлено отображение событий в UTC

🔖 <b>Следите за новостями!</b>
• Официальный сайт: https://arcreaiders.com  
• Discord: https://discord.gg/arc-raiders
"""

# === ПАРСИНГ СОБЫТИЙ ИЗ HTML ===
def parse_events_from_html(html_text):
    events = []
    lines = [line.strip() for line in html_text.splitlines() if line.strip()]

    try:
        i_active = lines.index("Active now")
        i_upcoming = lines.index("Upcoming next")
    except ValueError:
        i_active = -1
        i_upcoming = len(lines)

    # Активные события
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
                    for ev in EVENTS_RU:
                        if name_loc.startswith(ev):
                            loc = name_loc[len(ev):].strip()
                            if loc:
                                events.append({
                                    'name': ev,
                                    'location': loc,
                                    'info': f"Заканчивается через {time_left}",
                                    'type': 'active'
                                })
                            break
            i += 1

    # Предстоящие события
    if i_upcoming != -1:
        i = i_upcoming + 1
        while i < len(lines) and not lines[i].startswith("####"):
            line = lines[i]
            if line.startswith("!") or not line:
                i += 1
                continue
            if "Starts in" in line:
                parts = line.split(" Starts in ", 1)
                if len(parts) == 2:
                    name_loc = parts[0].strip()
                    time_left = parts[1].strip()
                    for ev in EVENTS_RU:
                        if name_loc.startswith(ev):
                            loc = name_loc[len(ev):].strip()
                            if loc:
                                events.append({
                                    'name': ev,
                                    'location': loc,
                                    'info': f"Начнётся через {time_left}",
                                    'type': 'upcoming'
                                })
                            break
            i += 1

    return events

# === TELEGRAM ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Все события", callback_data="events")
    kb.button(text="🆕 Обновления игры", callback_data="updates")
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="💰 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события и новости", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "events")
async def events_handler(callback: CallbackQuery):
    await callback.answer()
    import requests
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(URL, headers=headers, timeout=10)
        resp.raise_for_status()
        events = parse_events_from_html(resp.text)
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка загрузки: {e}")
        return

    if not events:
        msg = "🕗 Нет событий."
    else:
        active = [e for e in events if e['type'] == 'active']
        upcoming = [e for e in events if e['type'] == 'upcoming']
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
    kb.button(text="🆕 Обновления", callback_data="updates")
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

@router.callback_query(lambda c: c.data == "updates")
async def updates_handler(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="updates")
    kb.button(text="📅 Все события", callback_data="events")
    kb.button(text="⬅️ Назад", callback_data="start")
    kb.adjust(2)
    await callback.message.edit_text(GAME_UPDATES, parse_mode="HTML", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "start")
async def back_to_start(callback: CallbackQuery):
    await start_handler(callback.message)

dp.include_router(router)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ ARC Raiders Telegram-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())