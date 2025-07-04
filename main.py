import asyncio
import uuid
import pytz
from datetime import datetime, time, date, timedelta
from aiogram import Bot, types
from aiogram.filters import Command
from config import dp, bot
from database import db
from scheduler import scheduler, start_scheduler

async def send_reminder(user_id: int, text: str, job_id: str):
    """Отправка напоминания пользователю"""
    try:
        await bot.send_message(user_id, f"⏰ Напоминание: {text}")
        await db.deactivate_reminder(job_id)
        print(f"Отправлено напоминание пользователю {user_id}")
    except Exception as e:
        print(f"Ошибка отправки напоминания: {e}")

async def restore_reminders():
    """Восстановление активных напоминаний"""
    try:
        async with db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT r.*, u.telegram_id 
                    FROM reminders r
                    JOIN users u ON r.user_id = u.id
                    WHERE r.is_active = TRUE
                    AND (r.reminder_date > CURDATE() 
                         OR (r.reminder_date = CURDATE() 
                             AND r.reminder_time > CURTIME()))
                """)
                
                reminders = await cursor.fetchall()
                for reminder in reminders:
                    reminder_datetime = datetime.combine(
                        reminder['reminder_date'],
                        reminder['reminder_time']
                    ).astimezone(pytz.UTC)
                    
                    scheduler.add_job(
                        send_reminder,
                        'date',
                        run_date=reminder_datetime,
                        args=(reminder['telegram_id'], reminder['text'], reminder['job_id']),
                        id=reminder['job_id']
                    )
                print(f"Восстановлено {len(reminders)} напоминаний")
    except Exception as e:
        print(f"Ошибка восстановления: {e}")

async def on_startup():
    """Инициализация бота"""
    try:
        print(f"Текущее время сервера (UTC): {datetime.now(pytz.UTC)}")
        await db.connect()
        await db.init_db()
        start_scheduler()
        await restore_reminders()
        print("✅ Бот успешно запущен")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        raise

async def on_shutdown():
    """Завершение работы"""
    await db.close()
    print("Бот остановлен")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот-напоминалка.\n"
        "Создать напоминание:\n"
        "/remind HH:MM Текст\n"
        "/remind ГГГГ-ММ-ДД HH:MM Текст\n\n"
        "Мои напоминания: /my_reminders"
    )

@dp.message(Command("remind"))
async def cmd_remind(message: types.Message):
    """Обработчик напоминаний"""
    try:
        text = message.text.replace('/remind', '').strip()
        parts = text.split(maxsplit=1)
        
        if len(parts) < 2:
            raise ValueError("Не указан текст напоминания")
        
        time_part, reminder_text = parts
        
        # Обработка времени
        if ':' in time_part:
            time_str = time_part
            reminder_time = datetime.strptime(time_str, '%H:%M').time()
            reminder_date = date.today()
            
            # Проверка времени
            reminder_datetime = datetime.combine(reminder_date, reminder_time).astimezone(pytz.UTC)
            if reminder_datetime < datetime.now(pytz.UTC):
                reminder_date += timedelta(days=1)
        else:
            datetime_parts = time_part.split()
            if len(datetime_parts) != 2:
                raise ValueError("Неверный формат времени")
            
            date_str, time_str = datetime_parts
            reminder_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            reminder_time = datetime.strptime(time_str, '%H:%M').time()
            
            # Проверка времени
            reminder_datetime = datetime.combine(reminder_date, reminder_time).astimezone(pytz.UTC)
            if reminder_datetime < datetime.now(pytz.UTC):
                raise ValueError("Указанное время уже прошло")
        
        # Создание напоминания
        job_id = str(uuid.uuid4())
        user_id = await db.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Сохранение в БД
        if not await db.add_reminder(
            user_id=user_id,
            text=reminder_text,
            reminder_time=reminder_time.strftime('%H:%M:%S'),
            reminder_date=reminder_date,
            job_id=job_id
        ):
            await message.answer("❌ Ошибка сохранения")
            return
        
        # Планирование
        reminder_datetime = datetime.combine(reminder_date, reminder_time).astimezone(pytz.UTC)
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=reminder_datetime,
            args=(message.from_user.id, reminder_text, job_id),
            id=job_id
        )
        
        await message.answer(
            f"✅ Напоминание на {reminder_date} {reminder_time.strftime('%H:%M')}:\n"
            f"{reminder_text}\n"
            f"ID: {job_id}"
        )
        
    except ValueError as e:
        await message.answer(
            f"⚠️ Ошибка: {e}\n\n"
            "Формат:\n"
            "/remind HH:MM Текст\n"
            "Или:\n"
            "/remind ГГГГ-ММ-ДД HH:MM Текст\n\n"
            "Примеры:\n"
            "/remind 18:00 Позвонить\n"
            "/remind 2023-12-31 23:59 Поздравление"
        )
    except Exception as e:
        print(f"Ошибка: {e}")
        await message.answer("⚠️ Непредвиденная ошибка")

@dp.message(Command("my_reminders"))
async def cmd_my_reminders(message: types.Message):
    """Показать напоминания"""
    user_id = await db.get_or_create_user(message.from_user.id)
    reminders = await db.get_user_reminders(user_id)
    
    if not reminders:
        await message.answer("Нет активных напоминаний")
        return
    
    response = "📅 Ваши напоминания:\n\n"
    for rem in reminders:
        response += (
            f"⏰ {rem['reminder_date']} {rem['reminder_time']}:\n"
            f"{rem['text']}\n"
            f"ID: {rem['job_id']}\n\n"
        )
    
    await message.answer(response)

async def main():
    await on_startup()
    await dp.start_polling(bot)
    await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Завершение работы')