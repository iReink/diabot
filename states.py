from aiogram.fsm.state import State, StatesGroup


class RegisterCat(StatesGroup):
    name = State()
    am_time = State()
    peak = State()
    pm_time = State()


class EditCat(StatesGroup):
    am_time = State()
    peak = State()
    pm_time = State()
    name = State()


class Measure(StatesGroup):
    value = State()
