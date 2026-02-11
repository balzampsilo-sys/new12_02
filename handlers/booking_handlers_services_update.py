"""Частичное обновление booking_handlers.py для отображения услуг"""

# Этот файл содержит обновленные версии функций
# Для интеграции: заменить соответствующие функции в booking_handlers.py

from datetime import datetime
from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import DAY_NAMES, TIMEZONE
from database.queries import Database
from keyboards.user_keyboards import MAIN_MENU
from utils.helpers import now_local

router = Router()


@router.message(F.text == "📋 Мои записи")
async def my_bookings_with_services(message: Message):
    """Список записей пользователя С ИНФОРМАЦИЕЙ ОБ УСЛУГАХ"""
    user_id = message.from_user.id
    
    # ✅ P2: Получаем записи С услугами
    bookings = await Database.get_user_bookings(user_id)

    if not bookings:
        await message.answer("📭 У вас нет активных записей", reply_markup=MAIN_MENU)
        return

    text = "📋 ВАШИ АКТИВНЫЕ ЗАПИСИ:\n\n"
    keyboard = []
    now = now_local()

    for i, booking_data in enumerate(bookings, 1):
        # ✅ P2: Распаковываем все поля (включая service_name, duration, price)
        (
            booking_id,
            date_str,
            time_str,
            username,
            created_at,
            service_id,
            service_name,
            duration_minutes,
            price
        ) = booking_data
        
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        booking_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        booking_dt = booking_dt.replace(tzinfo=TIMEZONE)
        
        days_left = (booking_dt.date() - now.date()).days
        day_name = DAY_NAMES[date_obj.weekday()]
        
        # ✅ P2: Отображаем услугу в записи
        text += f"{i}. 📝 {service_name}\n"
        text += f"   ⏱ {duration_minutes} мин | 💰 {price}\n"
        text += f"   📅 {date_obj.strftime('%d.%m')} ({day_name}) 🕒 {time_str}"
        
        if days_left == 0:
            text += " — 🔥 сегодня!\n"
        elif days_left == 1:
            text += " — завтра\n"
        else:
            text += f" — через {days_left} дн.\n"
        
        text += "\n"
        
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"❌ Отменить #{i}",
                    callback_data=f"cancel:{booking_id}"
                ),
                InlineKeyboardButton(
                    text=f"🔄 Перенести #{i}",
                    callback_data=f"reschedule:{booking_id}"
                ),
            ]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(text, reply_markup=kb)


# ✅ P2: Дополнительные функции для админки

async def schedule_view_with_services(message: Message):
    """Просмотр расписания с информацией об услугах (для админа)"""
    from collections import defaultdict
    from datetime import timedelta
    
    today = now_local()
    start_date = today.strftime("%Y-%m-%d")
    
    # ✅ P2: Получаем расписание С услугами
    schedule = await Database.get_week_schedule(start_date, days=7)
    
    # Группируем по датам
    schedule_by_date = defaultdict(list)
    for row in schedule:
        # row = (date, time, username, service_name, duration, price)
        date_str = row[0]
        time_str = row[1]
        username = row[2]
        service_name = row[3]
        duration = row[4]
        price = row[5]
        
        schedule_by_date[date_str].append((time_str, username, service_name, duration, price))
    
    text = "📅 РАСПИСАНИЕ НА НЕДЕЛЮ\n\n"
    
    for day_offset in range(7):
        current_date = today + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        bookings = schedule_by_date.get(date_str, [])
        
        if bookings:
            day_name = DAY_NAMES[current_date.weekday()]
            text += f"📆 {current_date.strftime('%d.%m')} ({day_name}) — {len(bookings)} зап.\n"
            
            for time_str, username, service_name, duration, price in bookings:
                text += f"  🕒 {time_str} ({duration}м) - @{username}\n"
                text += f"      📝 {service_name} | 💰 {price}\n"
            
            text += "\n"
    
    if len(text.split("\n")) == 3:
        text += "📭 Нет записей на неделю"
    
    from keyboards.admin_keyboards import ADMIN_MENU
    await message.answer(text, reply_markup=ADMIN_MENU)
