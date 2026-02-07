import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)

import charts
import db
import notifications
import measure_flow
from help import help_router
from keyboards import (
    back_keyboard,
    cancel_keyboard,
    charts_menu_keyboard,
    inline_cancel_keyboard,
    main_menu_keyboard,
    measure_tags_keyboard,
    register_keyboard,
    settings_menu_keyboard,
)
from scheduler import schedule_daily_checks, schedule_procedure_reminders
from states import EditCat, Measure, RegisterCat
from utils import parse_measure, parse_peak, parse_time

router = Router()


def reminder_context(message: Message, state: FSMContext) -> FSMContext:
    return FSMContext(
        storage=state.storage,
        key=StorageKey(
            bot_id=message.bot.id,
            chat_id=message.chat.id,
            user_id=message.chat.id,
        ),
    )


async def handle_measure_value(message: Message, state: FSMContext) -> bool:
    # Запись замера и проверка уведомлений
    if not message.text:
        await message.answer("Нужно число, например 6.4")
        return False
    value = parse_measure(message.text)
    if value is None:
        await message.answer("Нужно число, например 6.4")
        return False

    data = await state.get_data()
    tag = data.get("tag", "OTHER")
    name = data.get("name")
    cat = db.get_cat_by_chat_and_name(message.chat.id, name) if name else None
    if not cat:
        await message.answer("Не найден пациент, начните с /start.")
        await state.clear()
        return True

    db.add_measure(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        name=name,
        amount=value,
        tag=tag,
    )

    await message.answer("Замер записан.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

    if value < 4:
        await message.answer(
            "❗ Срочно: значение ниже 4. Возможна гипогликемия. "
            "Уточните состояние питомца и действуйте по плану врача."
        )

    avg_glucose = notifications.average_glucose_last_days(message.chat.id, name, 7)
    if avg_glucose is not None and avg_glucose < 9:
        await message.answer("✅ Средняя глюкоза за 7 дней ниже 9 — прогресс к ремиссии!")

    if tag == "AMPS" and value > 10:
        await message.answer(
            f"Показатель выше 10. Не забудьте инсулин в {cat['am_time']}."
        )
    if tag == "PMPS" and value > 10:
        await message.answer(
            f"Показатель выше 10. Не забудьте инсулин в {cat['pm_time']}."
        )
    return True


def load_token() -> str:
    # Токен бота хранится в файле secret рядом с проектом
    return Path("secret").read_text(encoding="utf-8").strip()


def main_menu_text(cat_name: str) -> str:
    return (
        f"Привет! Это главное меню пациента {cat_name}.\n\n"
        "Выберите раздел ниже или введите /measure для ручного замера."
    )


def charts_menu_text() -> str:
    return (
        "Выберите график: \n"
        "• Суточная кривая — все замеры по дням за месяц.\n"
        "• Nadir — минимальные значения сахара по дням.\n"
        "• AMPS/PMPS — утро и вечер по каждому дню.\n"
        "• % в 4–10 — доля целевых замеров за 7 дней."
    )


def settings_menu_text(cat) -> str:
    return (
        "🛠️ Меню редактирования пациента\n\n"
        f"Имя: {cat['name']}\n"
        f"Утреннее время: {cat['am_time']}\n"
        f"Пик (часы): {cat['peak']}\n"
        f"Вечернее время: {cat['pm_time']}\n"
        f"Активно: {'да' if cat['is_active'] else 'нет'}"
    )


def _stats_labels(cat) -> dict[str, str]:
    am_time = cat["am_time"]
    pm_time = cat["pm_time"]
    peak_hours = int(cat["peak"])
    base = datetime.strptime(am_time, "%H:%M")
    peak_time = (base + timedelta(hours=peak_hours)).time().strftime("%H:%M")
    return {
        "AMPS": f"AMPS ({am_time})",
        "PEAK": f"PEAK ({peak_time})",
        "PMPS": f"PMPS ({pm_time})",
    }


@router.message(CommandStart())
async def start(message: Message):
    # Проверяем, есть ли пациент в текущем чате
    cat = db.get_cat_by_chat(message.chat.id)
    if not cat:
        text = (
            "Привет! Я помогу вести дневник сахара и строить графики.\n"
            "Мы начнём с регистрации пациента, это займёт пару минут."
        )
        await message.answer(text, reply_markup=register_keyboard())
        return

    await message.answer(main_menu_text(cat["name"]), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery):
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        text = (
            "Привет! Я помогу вести дневник сахара и строить графики.\n"
            "Нажмите кнопку ниже, чтобы зарегистрировать пациента."
        )
        await callback.message.edit_text(text, reply_markup=register_keyboard())
    else:
        await callback.message.edit_text(
            main_menu_text(cat["name"]), reply_markup=main_menu_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data == "menu:charts")
async def menu_charts(callback: CallbackQuery):
    await callback.message.edit_text(charts_menu_text(), reply_markup=charts_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery):
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return
    await callback.message.edit_text(settings_menu_text(cat), reply_markup=settings_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery):
    # Статистика — отдельный вывод без подменю
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    rows = db.get_measures(chat_id=callback.message.chat.id, name=cat["name"], days=60)
    if not rows:
        await callback.answer("Пока нет данных для статистики.", show_alert=True)
        return

    avg_glucose = notifications.average_glucose_last_days(
        callback.message.chat.id, cat["name"], 7
    )
    avg_nadir = notifications.average_nadir_last_days(
        callback.message.chat.id, cat["name"], 7
    )

    message_text = "Статистика за последние дни:\n"
    if avg_glucose is not None:
        mark = "✅" if avg_glucose < 9 else "❌"
        message_text += f"{mark} Средняя глюкоза за 7 дней: {avg_glucose:.1f}\n"
    if avg_nadir is not None:
        mark = "✅" if avg_nadir < 6 else "❌"
        message_text += f"{mark} Средний nadir за 7 дней: {avg_nadir:.1f}\n"

    await callback.message.answer(message_text)

    tables = charts.stats_table(rows, labels=_stats_labels(cat))
    for table in tables:
        await callback.message.answer_photo(BufferedInputFile(table.getvalue(), filename="stats.png"))

    await callback.answer()


@router.callback_query(F.data == "chart:daily")
async def chart_daily(callback: CallbackQuery):
    # Суточная кривая за последний месяц
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    rows = db.get_measures(chat_id=callback.message.chat.id, name=cat["name"], days=30)
    if not rows:
        await callback.answer("Недостаточно данных для графика.", show_alert=True)
        return

    image = charts.daily_curve(rows)
    await callback.message.answer_photo(BufferedInputFile(image.getvalue(), filename="daily.png"))
    await callback.answer()


@router.callback_query(F.data == "chart:nadir")
async def chart_nadir(callback: CallbackQuery):
    # Nadir за последние 60 дней
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    rows = db.get_measures(chat_id=callback.message.chat.id, name=cat["name"], days=60)
    if not rows:
        await callback.answer("Недостаточно данных для графика.", show_alert=True)
        return

    image = charts.nadir_chart(rows)
    await callback.message.answer_photo(BufferedInputFile(image.getvalue(), filename="nadir.png"))
    await callback.answer()


@router.callback_query(F.data == "chart:amps_pmps")
async def chart_amps_pmps(callback: CallbackQuery):
    # AMPS/PMPS за последние 60 дней
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    rows = db.get_measures(chat_id=callback.message.chat.id, name=cat["name"], days=60)
    if not rows:
        await callback.answer("Недостаточно данных для графика.", show_alert=True)
        return

    amps, pmps = charts.amps_pmps_chart(rows)
    await callback.message.answer_photo(BufferedInputFile(amps.getvalue(), filename="amps.png"))
    await callback.message.answer_photo(BufferedInputFile(pmps.getvalue(), filename="pmps.png"))
    await callback.answer()


@router.callback_query(F.data == "chart:range")
async def chart_range(callback: CallbackQuery):
    # Процент в целевом диапазоне 4–10
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    rows = db.get_measures(chat_id=callback.message.chat.id, name=cat["name"], days=60)
    if not rows:
        await callback.answer("Недостаточно данных для графика.", show_alert=True)
        return

    image = charts.range_percent_chart(rows)
    await callback.message.answer_photo(BufferedInputFile(image.getvalue(), filename="range.png"))
    await callback.answer()


@router.callback_query(F.data == "register:start")
async def register_start(callback: CallbackQuery, state: FSMContext):
    # Запускаем регистрацию пациента
    if db.get_cat_by_chat(callback.message.chat.id):
        await callback.answer("Пациент уже зарегистрирован.", show_alert=True)
        return

    await state.set_state(RegisterCat.name)
    await callback.message.answer(
        "Введите имя пациента (кличка кота).",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(RegisterCat.name)
async def register_name(message: Message, state: FSMContext):
    # Шаг 1: имя пациента
    name = message.text.strip()
    if not name or len(name) > 30:
        await message.answer("Имя должно быть не пустым и до 30 символов.")
        return

    await state.update_data(name=name)
    await state.set_state(RegisterCat.am_time)
    await message.answer(
        "Укажите время утренних процедур (формат HH:MM).\n"
        "Это время, когда обычно измеряете сахар и кормите.",
        reply_markup=cancel_keyboard(),
    )


@router.message(RegisterCat.am_time)
async def register_am_time(message: Message, state: FSMContext):
    # Шаг 2: утреннее время
    time_str = parse_time(message.text)
    if not time_str:
        await message.answer("Неверный формат. Пример: 07:30")
        return

    await state.update_data(am_time=time_str)
    await state.set_state(RegisterCat.peak)
    await message.answer(
        "Через сколько часов после утреннего инсулина наступает пик?\n"
        "Введите целое число от 1 до 12.",
        reply_markup=cancel_keyboard(),
    )


@router.message(RegisterCat.peak)
async def register_peak(message: Message, state: FSMContext):
    # Шаг 3: время пика в часах
    peak = parse_peak(message.text)
    if peak is None:
        await message.answer("Нужен целый час, например 4.")
        return

    await state.update_data(peak=peak)
    await state.set_state(RegisterCat.pm_time)
    await message.answer(
        "Укажите время вечерних процедур (формат HH:MM).",
        reply_markup=cancel_keyboard(),
    )


@router.message(RegisterCat.pm_time)
async def register_pm_time(message: Message, state: FSMContext):
    # Шаг 4: вечернее время и сохранение пациента
    time_str = parse_time(message.text)
    if not time_str:
        await message.answer("Неверный формат. Пример: 19:00")
        return

    data = await state.get_data()
    db.create_cat(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        name=data["name"],
        am_time=data["am_time"],
        peak=data["peak"],
        pm_time=time_str,
    )
    await state.clear()
    await message.answer(
        "Пациент зарегистрирован! Теперь можно добавлять замеры и строить графики.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        main_menu_text(data["name"]),
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("settings:"))
async def settings_edit(callback: CallbackQuery, state: FSMContext):
    # Выбираем, какой параметр редактировать
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    await state.update_data(name=cat["name"])

    if action == "name":
        await state.set_state(EditCat.name)
        await callback.message.answer("Введите новое имя пациента.", reply_markup=cancel_keyboard())
    elif action == "am_time":
        await state.set_state(EditCat.am_time)
        await callback.message.answer("Новое утреннее время (HH:MM).", reply_markup=cancel_keyboard())
    elif action == "peak":
        await state.set_state(EditCat.peak)
        await callback.message.answer("Новое время пика (целые часы).", reply_markup=cancel_keyboard())
    elif action == "pm_time":
        await state.set_state(EditCat.pm_time)
        await callback.message.answer("Новое вечернее время (HH:MM).", reply_markup=cancel_keyboard())

    await callback.answer()


@router.message(EditCat.name)
async def edit_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if not new_name or len(new_name) > 30:
        await message.answer("Имя должно быть не пустым и до 30 символов.")
        return

    data = await state.get_data()
    db.rename_cat(message.chat.id, data["name"], new_name)
    await state.clear()
    await message.answer(
        "Имя обновлено.", reply_markup=ReplyKeyboardRemove()
    )


@router.message(EditCat.am_time)
async def edit_am_time(message: Message, state: FSMContext):
    time_str = parse_time(message.text)
    if not time_str:
        await message.answer("Неверный формат. Пример: 07:30")
        return

    data = await state.get_data()
    db.update_cat_field(message.chat.id, data["name"], "am_time", time_str)
    await state.clear()
    await message.answer("Утреннее время обновлено.", reply_markup=ReplyKeyboardRemove())


@router.message(EditCat.peak)
async def edit_peak(message: Message, state: FSMContext):
    peak = parse_peak(message.text)
    if peak is None:
        await message.answer("Нужен целый час, например 4.")
        return

    data = await state.get_data()
    db.update_cat_field(message.chat.id, data["name"], "peak", peak)
    await state.clear()
    await message.answer("Время пика обновлено.", reply_markup=ReplyKeyboardRemove())


@router.message(EditCat.pm_time)
async def edit_pm_time(message: Message, state: FSMContext):
    time_str = parse_time(message.text)
    if not time_str:
        await message.answer("Неверный формат. Пример: 19:00")
        return

    data = await state.get_data()
    db.update_cat_field(message.chat.id, data["name"], "pm_time", time_str)
    await state.clear()
    await message.answer("Вечернее время обновлено.", reply_markup=ReplyKeyboardRemove())


@router.message(Command("measure"))
async def measure_start(message: Message, state: FSMContext):
    # Ручной ввод замера через команду
    cat = db.get_cat_by_chat(message.chat.id)
    if not cat:
        await message.answer("Сначала зарегистрируйте пациента командой /start.")
        return

    await state.clear()
    await state.update_data(name=cat["name"])
    await message.answer(
        "Выберите тег измерения:",
        reply_markup=measure_tags_keyboard(),
    )


@router.callback_query(F.data.startswith("measure:") & (F.data != "measure:cancel"))
async def measure_tag(callback: CallbackQuery, state: FSMContext):
    cat = db.get_cat_by_chat(callback.message.chat.id)
    if not cat:
        await callback.answer("Сначала зарегистрируйте пациента.", show_alert=True)
        return

    tag = callback.data.split(":", 1)[1]
    await state.set_state(Measure.value)
    await state.update_data(tag=tag, name=cat["name"])
    await callback.message.answer(
        f"Введите значение сахара для тега {tag} (например 5.6):",
        reply_markup=inline_cancel_keyboard(),
    )
    await callback.answer()


@router.message(Measure.value)
async def measure_value(message: Message, state: FSMContext):
    await handle_measure_value(message, state)


@router.message(F.text & ~F.text.startswith("/"))
async def measure_value_from_reminder(message: Message, state: FSMContext):
    if not message.text:
        return
    if message.text.casefold() == "отмена":
        return
    reminder_state = reminder_context(message, state)
    if await reminder_state.get_state() == Measure.value.state:
        await handle_measure_value(message, reminder_state)
        return
    pending = measure_flow.get_pending_measure(message.chat.id)
    if not pending:
        return
    await reminder_state.update_data(tag=pending.tag, name=pending.name)
    was_saved = await handle_measure_value(message, reminder_state)
    if was_saved:
        measure_flow.clear_pending_measure(message.chat.id)


@router.callback_query(F.data == "measure:cancel")
async def measure_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await reminder_context(callback.message, state).clear()
    measure_flow.clear_pending_measure(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    await callback.answer()


@router.message(F.text.casefold() == "отмена")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await reminder_context(message, state).clear()
    measure_flow.clear_pending_measure(message.chat.id)
    await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())


async def on_startup(bot: Bot, dispatcher: Dispatcher):
    # Запускаем фоновые задачи уведомлений
    asyncio.create_task(schedule_daily_checks(bot))
    asyncio.create_task(schedule_procedure_reminders(bot, dispatcher.fsm.storage))


async def main():
    token = load_token()
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    dispatcher.include_router(help_router)
    dispatcher.startup.register(on_startup)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
