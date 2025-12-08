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
    "Night Raid": "Ночной Рейд",
    "Uncovered Caches": "Обнаруженные Тайники",
    "Electromagnetic Storm": "Электромагнитная Буря",
    "Harvester": "Сборщик(Королева)",
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

# === РАСПИСАНИЕ (время в Москве — UTC+3) ===
SCHEDULE = [
    # (час_начала_мск, событие, карта)




    (0, "Night Raid", "Buried City"),
    (0, "Matriarch", "Spaceport"),

    (1, "Electromagnetic Storm", "Blue Gate"),
    (1,"Night Raid", "Stella Montis"),
    (1,"Night Raid", "Spaceport"),

    (2, "Prospecting Probes", "Buried City"),
    (2,  "Uncovered Caches", "Dam"),
    (2, "Night Raid", "Stella Montis"),
    (2, "Electromagnetic Storm", "Dam"),
    (2, "Matriarch", "Blue Gate"),

    (3, "Matriarch", "Dam"),
    (3, "Night Raid", "Buried City"),
    (3, "Harvester", "Spaceport"),

    (4, "Night Raid", "Spaceport"),

    (5, "Night Raid", "Dam"),
    (5, "Night Raid", "Stella Montis"),
    (5, "Uncovered Caches", "Buried City"),
    (5, "Husk Graveyard", "Blue Gate"),


    (6, "Lush Blooms", "Dam"),
    (6, "Night Raid", "Buried City"),
    (6, "Matriarch", "Spaceport"),

    (7, "Electromagnetic Storm", "Spaceport"),
    (7, "Night Raid", "Blue Gate"),

    (8, "Electromagnetic Storm", "Dam"),
    (8, "Husk Graveyard", "Buried City"),
    (8, "Harvester", "Blue Gate"),
    (8, "Night Raid", "Stella Montis"),

    (9, "Launch Tower Loot", "Spaceport"),
    (9, "Prospecting Probes", "Dam"),
    (9, "Night Raid", "Buried City"),

    (10, "Electromagnetic Storm", "Blue Gate"),
    (10, "Night Raid", "Spaceport"),

    (11, "Night Raid", "Dam"),
    (11, "Lush Blooms", "Buried City"),
    (11, "Prospecting Probes", "Blue Gate"),
    (11, "Night Raid", "Stella Montis"),

    (12, "Harvester", "Dam"),
    (12, "Night Raid", "Buried City"),
    (12, "Prospecting Probes", "Spaceport"),
    (12, "Lush Blooms", "Blue Gate"),

    (13, "Husk Graveyard", "Dam"),
    (13, "Hidden Bunker", "Spaceport"),
    (13, "Night Raid", "Blue Gate"),

    (14, "Electromagnetic Storm", "Dam"),
    (14, "Prospecting Probes", "Buried City"),
    (14, "Matriarch", "Blue Gate"),
    (14, "Night Raid", "Stella Montis"),

    (15, "Lush Blooms", "Spaceport"),
    (15, "Night Raid", "Buried City"),

    (16, "Prospecting Probes", "Dam"),
    (16, "Night Raid", "Spaceport"),


    (17, "Night Raid", "Dam"),
    (17, "Husk Graveyard", "Buried City"),
    (17, "Uncovered Caches", "Blue Gate"),
    (17, "Night Raid", "Stella Montis"),

    (18, "Uncovered Caches", "Spaceport"),
    (18, "Night Raid", "Buried City"),

    (19, "Harvester", "Dam"),
    (19, "Electromagnetic Storm", "Spaceport"),
    (19, "Electromagnetic Storm", "Blue Gate"),

    (20, "Harvester", "Blue Gate"),
    (20, "Electromagnetic Storm", "Dam"),
    (20, "Lush Blooms", "Dam"),
    (20, "Lush Blooms", "Buried City"),
    (20, "Night Raid", "Stella Montis"),

    (21, "Night Raid", "Buried City"),
    (21, "Harvester", "Spaceport"),
    (21, "Husk Graveyard", "Blue Gate"),

    (22, "Hidden Bunker", "Spaceport"),
    (22, "Night Raid", "Blue Gate"),


    (21, "Prospecting Probes", "Buried City"),

    (22, "Husk Graveyard", "Blue Gate"),

    (23, "Matriarch", "Dam"),
    (23, "Uncovered Caches", "Buried City"),
    (23, "Lush Blooms", "Blue Gate"),

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

# === ОБНОВЛЕНИЯ ИГРЫ ===
GAME_UPDATES = """
🎮 <b>ARC Raiders — Последние обновления</b>



🔧 <b>Информация по Экспедиции</b>
• Экспедиция немного задержалась, и доступ откроется 17 декабря. У вас будет шестидневный период, в течение которого ваш Рейдер сможет навсегда покинуть Ржавый Пояс. Отправившись в Караване, который вы построили в Проекте Экспедиции, вы начнёте своё путешествие заново с определёнными баффами. Мы хотим рассказать вам о некоторых из них.
Когда вы отправитесь в экспедицию, все предметы из тайника вашего рейдера будут переданы в ее распоряжение. Ваш следующий рейдер может заработать до пяти очков навыков в зависимости от общей стоимости вашего тайника и монет на момент отправления. Стоимость одного миллиона монет равна одному дополнительному очку навыка для вашего нового рейдера.
При вайпе все, что связано с вашим прогрессом, будет сброшено. Это означает, что ваше дерево навыков, уровень, тайник, мастерская, способности к крафту и чертежи. Стоит уточнить, что все карты и возможные улучшения в мастерской будут доступны сразу после вайпа.
Ваш новый рейдер не будет полностью перезапущен с самого начала. Сбросив настройки, вы получите следующие преимущества и награды:

Постоянные награды:
Скин "Латочник"
•Потрепанная кепка Плюшкина
•Значок индикатора экспедиций
•Очки умений (в зависимости от стоимости хранилища)
•+12 места в тайнике

Временные бонусы:
•10% бонус к ремонту
•5% бонус к опыту
•На 6% больше материалов у Плюшкина

Хотя очки умений, дополнительное место в тайнике и косметика доступны постоянно, срок действия улучшений аккаунта истечет, если вы решите не отправляться в следующую экспедицию. Имейте в виду, что в течение следующих трех экспедиций количество баффов увеличится (но в течение каждого периода экспедиции разрешается только один выход!).
Помните, что период проведения экспедиции будет открыт с 17 декабря и продлится до 22 декабря. Вы должны зарегистрироваться в течение этого периода, и все участники автоматически отправятся в одно и то же время 22-го числа.
Стоимость вашего хранилища и монет будет подсчитана, когда закроется окно, поэтому не прекращайте лутаться до этого времени! Если вы решите не вайпать ваш аккаунт в этот раз, не волнуйтесь - ваш прогресс в строительстве фургона будет сохранен, так что вы сможете продолжать работать над ним до тех пор, пока через пару месяцев не откроется следующее окно.




🔗 <b>Официальные ресурсы</b>
• Сайт: https://arcreaiders.com  
• Discord: https://discord.gg/arc-raiders
"""

# === TELEGRAM ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 События", callback_data="events")
    kb.button(text="🆕 Обновления игры", callback_data="updates")
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await message.answer("🎮 ARC Raiders: события (по расписанию)", reply_markup=kb.as_markup())

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
    kb.button(text="🆕 Обновления", callback_data="updates")
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.button(text="⬅️ Назад", callback_data="start")
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
    kb.button(text="📺 Стрим", url=STREAM_URL)
    kb.button(text="📢 Канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.button(text="⬅️ Назад", callback_data="start")
    kb.adjust(2)

    await callback.message.edit_text(GAME_UPDATES, parse_mode="HTML", reply_markup=kb.as_markup())

@router.callback_query(lambda c: c.data == "start")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 События", callback_data="events")
    kb.button(text="🆕 Обновления игры", callback_data="updates")
    kb.button(text="📺 Мой стрим", url=STREAM_URL)
    kb.button(text="📢 Мой канал", url=CHANNEL_URL)
    kb.button(text="🛠 Поддержка", url=SUPPORT_URL)
    kb.adjust(2)
    await callback.message.edit_text("🎮 ARC Raiders: события (по расписанию из Excel)", reply_markup=kb.as_markup())

dp.include_router(router)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ ARC Raiders Telegram-бот запущен (с кнопкой 'Назад')")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
