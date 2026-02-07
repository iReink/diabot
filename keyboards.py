from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Графики", callback_data="menu:charts")],
            [InlineKeyboardButton(text="Статистика", callback_data="menu:stats")],
            [InlineKeyboardButton(text="Настройки пациента", callback_data="menu:settings")],
        ]
    )


def register_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Зарегистрировать пациента", callback_data="register:start")]]
    )


def back_keyboard(target: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="< Назад", callback_data=target)]]
    )


def charts_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="< Назад", callback_data="menu:main")],
            [InlineKeyboardButton(text="Суточная кривая", callback_data="chart:daily")],
            [InlineKeyboardButton(text="Nadir", callback_data="chart:nadir")],
            [InlineKeyboardButton(text="AMPS / PMPS", callback_data="chart:amps_pmps")],
            [InlineKeyboardButton(text="% в диапазоне 4–10", callback_data="chart:range")],
        ]
    )


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="< Назад", callback_data="menu:main")],
            [InlineKeyboardButton(text="Изменить имя", callback_data="settings:name")],
            [InlineKeyboardButton(text="Утреннее время", callback_data="settings:am_time")],
            [InlineKeyboardButton(text="Время пика", callback_data="settings:peak")],
            [InlineKeyboardButton(text="Вечернее время", callback_data="settings:pm_time")],
        ]
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def inline_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="measure:cancel")]]
    )


def measure_tags_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="AMPS", callback_data="measure:AMPS")],
            [InlineKeyboardButton(text="PEAK", callback_data="measure:PEAK")],
            [InlineKeyboardButton(text="PMPS", callback_data="measure:PMPS")],
            [InlineKeyboardButton(text="OTHER", callback_data="measure:OTHER")],
        ]
    )
