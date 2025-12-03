import asyncio
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === НАСТРОЙКИ ===
BOT_TOKEN = "8278278864:AAFcWknKDxHS77Gbp6Re_DMEZn9hR3wb2qs"
STREAM_URL = "https://www.twitch.tv/silovik_"
CHANNEL_URL = "https://t.me/silovik_stream"
SUPPORT_URL = "https://dalink.to/silovik_"

# === РАСПИСАНИЕ СОБЫТИЙ (UTC) ===
EVENT_SCHEDULE = [
    # (начало_часа, событие, [карты])
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

# === ПЕРЕВОДЫ ===
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

# === ВЫЧИСЛЕНИЕ СОБЫТИЙ ===
def get_current_events():
    """Возвращает активные и предстоящие события на основе текущего UTC-времени."""
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    minutes = now.minute
    seconds = now.second
    total_seconds = minutes * 60 + seconds

    active = []
    upcoming = []

    # Проверяем все события за текущий и следующий час
    for hour, event, maps in EVENT_SCHEDULE:
        if hour == current_hour:
            # Событие идёт сейчас (если прошло < 3600 сек)
            if total_seconds < 3600:
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
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события по картам", reply_markup=kb.as_markup())


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
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)

    # Обход ошибки "message is not modified"
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
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())

