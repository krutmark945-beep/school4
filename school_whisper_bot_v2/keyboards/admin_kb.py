from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_main_kb(is_chief: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Младшие админы"), KeyboardButton(text="🚫 Заблокированные")],
            [KeyboardButton(text="📅 Отправить расписание")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Админ-панель",
    )
    if is_chief:
        kb.keyboard.append([KeyboardButton(text="🔧 Технические работы")])
        kb.keyboard.append([KeyboardButton(text="🏫 Добавить мероприятие")])
        kb.keyboard.append([KeyboardButton(text="🗑 Удалить мероприятие")])
        kb.keyboard.append([KeyboardButton(text="📢 Рассылка")])
        kb.keyboard.append([KeyboardButton(text="📜 История рассылок")])
    return kb


def get_back_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True,
    )
    return kb
