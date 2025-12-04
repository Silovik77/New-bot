import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timezone

# === НАСТРОЙКИ ===
BOT_TOKEN = "8278278864:AAFcWknKDxHS77Gbp6Re_DMEZn9hR3wb2qs"

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


# === СТАТИЧНОЕ РАСПИСАНИЕ СОБЫТИЙ (UTC) ===
EVENT_SCHEDULE = [
    # (час_UTC, событие, [карты])
    (20, "Lush Blooms", ["Blue Gate"]),
    (20, "Matriarch", ["Dam"]),
    (20, "Night Raid", ["Dam", "Stella Montis"]),
    (20, "Uncovered Caches", ["Buried City"]),

    (21, "Matriarch", ["Spaceport"]),
    (21, "Night Raid", ["Buried City"]),

    (22, "Electromagnetic Storm", ["Blue Gate", "Dam", "Spaceport"]),

    (23, "Prospecting Probes", ["Buried City", "Dam", "Blue Gate", "Spaceport"]),

    (0, "Harvester", ["Dam"]),
    (0, "Launch Tower Loot", ["Spaceport"]),

    (1, "Hidden Bunker", ["Spaceport"]),

    (2, "Uncovered Caches", ["Blue Gate"]),

    (3, "Husk Graveyard", ["Dam"]),

    (4, "Electromagnetic Storm", ["Spaceport"]),
    (4, "Harvester", ["Spaceport"]),

    (5, "Lush Blooms", ["Buried City"]),
    (5, "Matriarch", ["Blue Gate"]),
    (5, "Husk Graveyard", ["Blue Gate"]),

    (6, "Launch Tower Loot", ["Spaceport"]),

    (7, "Hidden Bunker", ["Spaceport"]),
    (7, "Husk Graveyard", ["Buried City"]),

    (8, "Lush Blooms", ["Buried City"]),

    (9, "Matriarch", ["Spaceport"]),
    (9, "Prospecting Probes", ["Dam"]),
    (9, "Lush Blooms", ["Blue Gate"]),

    (10, "Electromagnetic Storm", ["Blue Gate"]),
    (10, "Husk Graveyard", ["Dam"]),
    (10, "Hidden Bunker", ["Spaceport"]),

    (11, "Prospecting Probes", ["Buried City"]),

    (12, "Harvester", ["Spaceport"]),

    (13, "Matriarch", ["Dam"]),

    (14, "Night Raid", ["Spaceport"]),

    (15, "Lush Blooms", ["Spaceport"]),

    (16, "Uncovered Caches", ["Dam"]),
    (16, "Husk Graveyard", ["Blue Gate"]),

    (17, "Electromagnetic Storm", ["Dam"]),
    (17, "Hidden Bunker", ["Blue Gate"]),

    (18, "Night Raid", ["Blue Gate"]),
    (18, "Prospecting Probes", ["Spaceport"]),

    (19, "Harvester", ["Blue Gate"]),
    (19, "Matriarch", ["Blue Gate"]),
]

# === ОБНОВЛЕНИЯ ИГРЫ ===
GAME_UPDATES = """
🎮 <b>ARC Raiders — Последние обновления</b>

🔖 <b>v1.2.5 (05.12.2025)</b>
• Исправлен баг с исчезающими ящиками в Плотине
• Уменьшен урон Жнеца на 15%
• Добавлена новая карта: Стелла Монтиc (на пробе)
• Оптимизация FPS на слабых ПК

🔖 <b>v1.2.4 (28.11.2025)</b>
• Исправлен вылет при входе в подземелья
• Снижена длительность Ночного Налёта с 2ч до 1ч
• Исправлено отображение событий в UTC

🔗 <b>Официальные ресурсы</b>
• Сайт: https://arcreaiders.com  
• Discord: https://discord.gg/arc-raiders
"""


# === ВЫЧИСЛЕНИЕ СОБЫТИЙ ===
def get_current_events():
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_seconds = minutes * 60 + seconds

    active = []
    upcoming = []

    for hour, event, maps in EVENT_SCHEDULE:
        if hour == current_hour and total_seconds < 3600:
            # Событие идёт сейчас
            time_left = 3600 - total_seconds
            mins, secs = divmod(time_left, 60)
            for loc in maps:
                active.append({
                    'name': event,
                    'location': loc,
                    'info': f"Заканчивается через {mins}m {secs}s"
                })
        elif (hour == (current_hour + 1) % 24):
            # Событие начнётся через (3600 - total_seconds) секунд
            time_until = 3600 - total_seconds
            mins, secs = divmod(time_until, 60)
            for loc in maps:
                upcoming.append({
                    'name': event,
                    'location': loc,
                    'info': f"Начнётся через {mins}m {secs}s"
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
    kb.button(text="🆕 Обновления игры", callback_data="updates")
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