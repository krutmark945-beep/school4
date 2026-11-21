from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Младшие админы"), KeyboardButton(text="🚫 Заблокированные")],
            [KeyboardButton(text="📅 Отправить расписание")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Админ-панель",
    )
    return kb


def get_back_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True,
    )
    return kb
