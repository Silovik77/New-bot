# ... (остальной код до функций и обработчиков остается без изменений: импорты, настройки, словари, LINKS, GAME_UPDATE_TEXT) ...

# --- Функции для получения и парсинга данных из HTML ---

def get_arc_raiders_events_from_html():
    """Получает и парсит события с HTML-страницы MetaForge."""
    try:
        # Добавим User-Agent, чтобы не казаться ботом
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(EVENT_TIMERS_URL, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        active_events = []
        upcoming_events = []

        current_time_utc = datetime.now(timezone.utc)

        # Находим секции "Active now" и "Upcoming next"
        active_section = soup.find(string=re.compile(r"Active now", re.IGNORECASE))
        if active_section:
            active_container = active_section.parent.parent.find_next_sibling('div')
            if active_container:
                active_items = active_container.find_all('div', recursive=False)
                for item in active_items:
                     # Проверяем, содержит ли div информацию о событии (обычно содержит img и span)
                     if item.find('img') and item.find('span'):
                        event_text = item.get_text(strip=True)
                        # Регулярное выражение для извлечения: [Название] [Локация] Ends in [Время]
                        match = re.search(r'([^(]+?)\s+([^(]+?)\s+Ends\s+in\s+([\d\w\s]+)', event_text, re.IGNORECASE)
                        if match:
                            name = match.group(1).strip()
                            location = match.group(2).strip()
                            time_left_str = match.group(3).strip()
                            # Вычисляем время окончания (приблизительно)
                            # parse_time_string нужно определить, как в предыдущем коде
                            time_left_delta = parse_time_string(time_left_str)
                            end_time_utc = current_time_utc + time_left_delta

                            active_events.append({
                                'name': name,
                                'location': location,
                                'time_left': time_left_str,
                                'end_time': end_time_utc
                            })
                            logger.info(f"Добавлено активное событие из HTML: {name} на {location}, осталось {time_left_str}")

        upcoming_section = soup.find(string=re.compile(r"Upcoming next", re.IGNORECASE))
        if upcoming_section:
            upcoming_container = upcoming_section.parent.parent.find_next_sibling('div')
            if upcoming_container:
                upcoming_items = upcoming_container.find_all('div', recursive=False)
                for item in upcoming_items:
                     # Проверяем, содержит ли div информацию о событии (обычно содержит img и span)
                     if item.find('img') and item.find('span'):
                        event_text = item.get_text(strip=True)
                        # Регулярное выражение для извлечения: [Название] [Локация] Starts in [Время]
                        match = re.search(r'([^(]+?)\s+([^(]+?)\s+Starts\s+in\s+([\d\w\s]+)', event_text, re.IGNORECASE)
                        if match:
                            name = match.group(1).strip()
                            location = match.group(2).strip()
                            time_to_start_str = match.group(3).strip()
                            # Вычисляем время начала (приблизительно)
                            time_to_start_delta = parse_time_string(time_to_start_str)
                            start_time_utc = current_time_utc + time_to_start_delta

                            upcoming_events.append({
                                'name': name,
                                'location': location,
                                'time_left': time_to_start_str,
                                'start_time': start_time_utc
                            })
                            logger.info(f"Добавлено предстоящее событие из HTML: {name} на {location}, начнётся через {time_to_start_str} ({start_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')})")

        # Обработка сложных событий типа Electromagnetic Storm (если они есть в HTML в таком формате)
        # Ищем div'ы после "Upcoming next", которые содержат заголовок (h4 или strong) и списки
        sections_after_upcoming = upcoming_container.find_next_siblings('div') if upcoming_container else []
        for section in sections_after_upcoming:
            title_elem = section.find(['h4', 'strong'])
            if title_elem:
                event_name = title_elem.get_text(strip=True)
                # Ищем "Starts in" в этом же div или ближайшем родителе
                starts_in_match = re.search(r'Starts\s+in\s+([\d\w\s]+)', section.get_text(), re.IGNORECASE)
                if starts_in_match:
                    time_to_start_str = starts_in_match.group(1).strip()
                    time_to_start_delta = parse_time_string(time_to_start_str)
                    start_time_utc = current_time_utc + time_to_start_delta

                    # Ищем "Upcoming windows"
                    windows_header = section.find(string=re.compile(r"Upcoming windows", re.IGNORECASE))
                    if windows_header:
                        windows_list = windows_header.parent.find_next_sibling('div')
                        if windows_list:
                            window_items = windows_list.find_all('div', recursive=False)
                            for window_item in window_items:
                                win_text = window_item.get_text(strip=True)
                                # Регулярное выражение для извлечения: [Время] [Локация] \n in [Время]
                                win_match = re.search(r'([\d:]+\s*[-–]\s*[\d:]+)\s+([^(]+?)\s+in\s+([\d\w\s]+)', win_text, re.IGNORECASE)
                                if win_match:
                                    time_period = win_match.group(1).strip()
                                    location = win_match.group(2).strip()
                                    time_to_window_str = win_match.group(3).strip()
                                    time_to_window_delta = parse_time_string(time_to_window_str)
                                    window_start_time_utc = current_time_utc + time_to_window_delta

                                    # Добавляем каждое окно как отдельное предстоящее событие
                                    upcoming_events.append({
                                        'name': event_name,
                                        'location': location,
                                        'time_left': time_to_window_str,
                                        'start_time': window_start_time_utc,
                                        'period': time_period
                                    })
                                    logger.info(f"Добавлено предстоящее окно сложного события из HTML: {event_name} на {location}, начнётся через {time_to_window_str} ({window_start_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')})")

        # Сортировка предстоящих событий по времени начала
        upcoming_events.sort(key=lambda x: x['start_time'])

        logger.info(f"Парсинг HTML завершён: {len(active_events)} активных, {len(upcoming_events)} предстоящих.")
        return active_events, upcoming_events

    except requests.RequestException as e:
        logger.error(f"Ошибка при получении данных с {EVENT_TIMERS_URL}: {e}")
        return [], []
    except Exception as e:
        logger.error(f"Ошибка при парсинге HTML: {e}")
        return [], []

# --- Функция для парсинга строки времени (например, '8m 48s', '1h 8m 48s') ---
def parse_time_string(time_str):
    """Преобразует строку времени (например, '8m 48s', '1h 8m 48s') в timedelta."""
    if not time_str:
        return timedelta(seconds=0)

    # Ищем часы, минуты и секунды в строке
    hours_match = re.search(r'(\d+)\s*h', time_str, re.IGNORECASE)
    minutes_match = re.search(r'(\d+)\s*m', time_str, re.IGNORECASE)
    seconds_match = re.search(r'(\d+)\s*s', time_str, re.IGNORECASE)

    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0

    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

# --- ОБНОВЛЁННАЯ функция отправки или редактирования сообщения с событиями ---
async def send_events_message(message: types.Message, edit: bool = False):
    # <-- ДОБАВЛЕНО ЛОГИРОВАНИЕ -->
    logger.info("Вызов send_events_message (парсинг HTML)")
    # МЕНЯЕМ: вызываем get_arc_raiders_events_from_html вместо get_arc_raiders_events_from_api_calculated
    active, upcoming = get_arc_raiders_events_from_html()
    logger.info(f"Получено из HTML: {len(active)} активных, {len(upcoming)} предстоящих.")

    # Форматируем активные события
    active_message = format_event_message(active, "active")
    # Форматируем ВСЕ предстоящие события (без ограничения)
    upcoming_message = format_event_message(upcoming, "upcoming")

    # Объединяем сообщения
    response_text = active_message
    if upcoming: # Добавляем предстоящие, только если они есть
        response_text += "\n" + upcoming_message

    # Клавиатура с кнопками "Обновить" и "Назад" (в главное меню)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_events")], # Изменили callback
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_menu")]
    ])

    if edit:
        # Пытаемся отредактировать существующее сообщение
        try:
            # parse_mode изменён на HTML
            await message.edit_text(text=response_text, reply_markup=keyboard, parse_mode='HTML')
            logger.info("Сообщение с событиями отредактировано.")
        except Exception as e:
            # Если не получилось отредактировать (например, сообщение слишком старое), отправим новое
            logger.warning(f"Не удалось отредактировать сообщение: {e}. Отправляем новое.")
            # parse_mode изменён на HTML
            await message.answer(response_text, reply_markup=keyboard, parse_mode='HTML')
    else:
        # Отправляем новое сообщение
        # parse_mode изменён на HTML
        await message.answer(response_text, reply_markup=keyboard, parse_mode='HTML')

# ... (остальные обработчики и функции остаются без изменений, включая format_event_message) ...