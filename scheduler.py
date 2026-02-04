from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from db import get_cat_by_chat_and_name, list_chats
from keyboards import cancel_keyboard
from states import Measure
from notifications import (
    amps_peak_difference_low,
    average_glucose_last_days,
    average_nadir_last_days,
    consecutive_nadir,
)


async def schedule_daily_checks(bot: Bot):
    # Ежедневные проверки в 23:59
    while True:
        now = datetime.now()
        next_run = now.replace(hour=23, minute=59, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        await run_daily_checks(bot)


async def run_daily_checks(bot: Bot):
    chats = list_chats()
    for row in chats:
        chat_id = row["chat_id"]
        name = row["name"]

        avg_nadir = average_nadir_last_days(chat_id, name, 7)
        if avg_nadir is not None and 5 < avg_nadir < 7:
            await bot.send_message(
                chat_id,
                "✅ Средний nadir за 7 дней в хорошем диапазоне — отличный прогресс к ремиссии!",
            )

        if consecutive_nadir(chat_id, name, 3, lambda v: v > 9):
            await bot.send_message(
                chat_id,
                "⚠️ Уже 3 дня подряд nadir выше 9. Возможно, текущая доза мала.",
            )

        if consecutive_nadir(chat_id, name, 5, lambda v: v < 5):
            await bot.send_message(
                chat_id,
                "⚠️ 5 дней подряд nadir ниже 5. Доза может быть слишком высокой — риск гипо.",
            )

        if amps_peak_difference_low(chat_id, name, 3):
            await bot.send_message(
                chat_id,
                "⚠️ Три дня подряд разница AMPS и PEAK меньше 2. Инсулин работает слабо.",
            )


async def schedule_procedure_reminders(bot: Bot, storage):
    # Напоминания каждые 60 секунд
    while True:
        now = datetime.now()
        await send_procedure_reminders(bot, storage, now)
        await asyncio.sleep(60)


async def send_procedure_reminders(bot: Bot, storage, now: datetime):
    chats = list_chats()
    for row in chats:
        chat_id = row["chat_id"]
        name = row["name"]
        cat = get_cat_by_chat_and_name(chat_id, name)
        if not cat:
            continue

        for tag, time_field, label in (
            ("AMPS", "am_time", "утреннее"),
            ("PMPS", "pm_time", "вечернее"),
        ):
            time_str = cat[time_field]
            target = now.replace(
                hour=int(time_str.split(":")[0]),
                minute=int(time_str.split(":")[1]),
                second=0,
                microsecond=0,
            )
            reminder_time = target - timedelta(minutes=15)
            if reminder_time <= now < reminder_time + timedelta(minutes=1):
                await bot.send_message(
                    chat_id,
                    f"⏰ Через 15 минут {label} замер. Пора измерить сахар и покормить.",
                )
                context = FSMContext(
                    storage=storage,
                    key=StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id),
                )
                await context.set_state(Measure.value)
                await context.update_data(tag=tag, name=name)
                await bot.send_message(
                    chat_id,
                    "Введите значение сахара (например 5.6):",
                    reply_markup=cancel_keyboard(),
                )

        # Пик: AMPS + peak (в часах)
        am_time = cat["am_time"]
        peak_hours = int(cat["peak"])
        am_target = now.replace(
            hour=int(am_time.split(":")[0]),
            minute=int(am_time.split(":")[1]),
            second=0,
            microsecond=0,
        )
        peak_time = am_target + timedelta(hours=peak_hours)
        reminder_time = peak_time - timedelta(minutes=15)
        if reminder_time <= now < reminder_time + timedelta(minutes=1):
            await bot.send_message(
                chat_id,
                "⏰ Через 15 минут время PEAK. Пора измерить сахар.",
            )
            context = FSMContext(
                storage=storage,
                key=StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=chat_id),
            )
            await context.set_state(Measure.value)
            await context.update_data(tag="PEAK", name=name)
            await bot.send_message(
                chat_id,
                "Введите значение сахара (например 5.6):",
                reply_markup=cancel_keyboard(),
            )
