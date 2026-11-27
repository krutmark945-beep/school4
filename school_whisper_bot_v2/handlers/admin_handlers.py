import logging
from datetime import datetime, timedelta
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from config import CHIEF_ADMIN_IDS, HIDDEN_ADMIN_IDS, SCHEDULE_CHANNEL_ID, SCHEDULE_COOLDOWN_HOURS
from database.db import Database
from keyboards.admin_kb import get_admin_main_kb, get_back_kb

logger = logging.getLogger(__name__)


def _get_db(message) -> Database:
    return message.bot.db  # type: ignore


# ---------------- FSM состояния ----------------

class AdminStates(StatesGroup):
    waiting_admin_add = State()       # ждём пересылку сообщения / ID / username для добавления админа
    waiting_admin_delete_id = State() # ждём ID для удаления админа

    # добавление школьного мероприятия
    waiting_event_title = State()     # название мероприятия
    waiting_event_desc = State()      # описание мероприятия
    waiting_event_date = State()      # дата мероприятия
    waiting_event_photo = State()     # фото мероприятия (опционально)

    # рассылка
    waiting_broadcast_text = State()  # текст рассылки


class ScheduleStates(StatesGroup):
    waiting_photo = State()


CANCEL_TEXT = "❌ Отмена"


# ---------------- глобальная отмена любого FSM-состояния ----------------

@dp.message_handler(commands=["cancel"], state="*")
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_admin_main_kb(is_chief=message.from_user.id in CHIEF_ADMIN_IDS),
    )


@dp.message_handler(lambda m: m.text == CANCEL_TEXT, state="*")
async def msg_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_admin_main_kb(is_chief=message.from_user.id in CHIEF_ADMIN_IDS),
    )


@dp.callback_query_handler(lambda c: c.data == "fsm_cancel", state="*")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.answer("❌ Отменено")
    await call.message.answer(
        "❌ Действие отменено.",
        reply_markup=get_admin_main_kb(is_chief=call.from_user.id in CHIEF_ADMIN_IDS),
    )


# ---------------- вход в админ-панель ----------------

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)

    if not is_admin:
        return
    role = "Главный администратор" if is_chief else "Младший администратор"
    await message.answer(
        f"🔐 Админ-панель\nРоль: {role}",
        reply_markup=get_admin_main_kb(is_chief=is_chief),
    )


# ---------------- список админов ----------------

@dp.message_handler(lambda m: m.text == "👥 Младшие админы")
async def admin_list_juniors(message: types.Message):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)

    if not is_admin:
        return

    admins = await db.get_admins()
    # Скрываем администраторов из списка HIDDEN_ADMIN_IDS (кроме chief — он всегда виден)
    admins = [a for a in admins if a["user_id"] not in HIDDEN_ADMIN_IDS or a["role"] == "chief"]
    if not admins:
        if is_chief:
            text = "👥 <b>Список администраторов:</b>\n\nМладших админов не найдено."
            kb_buttons = [
                [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
            ]
            kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
            await message.answer(text, reply_markup=kb)
            return
        await message.answer("Админов не найдено.", reply_markup=get_back_kb())
        return

    text = "👥 <b>Список администраторов:</b>\n\n"
    for a in admins:
        role_emoji = "👑" if a["role"] == "chief" else "👤"
        if a["role"] == "chief":
            role_label = "Главный администратор"
        elif a["role"] == "junior":
            role_label = "Младший администратор"
        else:
            role_label = a["role"]
        text += f"{role_emoji} ID: <code>{a['user_id']}</code> | @{a['username'] or '-'} | {role_label}\n"

    kb_buttons = []
    if is_chief:
        kb_buttons.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")])
        kb_buttons.append([InlineKeyboardButton(text="🗑 Удалить админа", callback_data="admin_delete")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb)


# ---------------- добавление админа через пересылку / ID / username ----------------

@dp.callback_query_handler(lambda c: c.data == "admin_add")
async def admin_add_start(call: types.CallbackQuery, state: FSMContext):
    is_chief = call.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await call.answer("⛔ Только для главного администратора", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_admin_add)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")]]
    )
    await call.message.answer(
        "📥 Перешлите любое сообщение от пользователя, которого хотите сделать админом,\n"
        "или пришлите его числовой ID,\n"
        "или username (без @).\n\n"
        "Нажмите «❌ Отмена», чтобы выйти.",
        reply_markup=cancel_kb,
    )
    await call.answer()


@dp.message_handler(state=AdminStates.waiting_admin_add)
async def admin_waiting_admin_add(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    # Кнопка отмены (текстовая)
    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=True))
        return

    user_id = None
    username = None

    # Способ 1: пересланное сообщение (надёжный способ — работает для любого контента)
    if message.forward_from:
        user_id = message.forward_from.id
        username = message.forward_from.username

    # Способ 2: текст — числовой ID или username
    elif message.text:
        raw = message.text.strip()
        if raw.startswith("@"):
            raw = raw[1:]

        # числовой ID — используем напрямую, без get_chat (безопаснее и надёжнее)
        if raw.lstrip("-").isdigit():
            try:
                user_id = int(raw)
            except ValueError:
                user_id = None
        else:
            # username — пробуем get_chat, но это работает не всегда для обычных пользователей
            try:
                chat = await bot.get_chat(raw)
                user_id = chat.id
                username = chat.username
            except Exception:
                await message.answer(
                    "❌ Не удалось найти пользователя по username.\n"
                    "Возможно, пользователь ещё не писал боту.\n"
                    "Перешлите любое его сообщение или пришлите числовой ID.",
                    reply_markup=get_admin_main_kb(is_chief=True),
                )
                await state.finish()
                return
    else:
        await message.answer(
            "Пришлите пересланное сообщение, числовой ID или username пользователя.",
            reply_markup=get_admin_main_kb(is_chief=True),
        )
        await state.finish()
        return

    if not user_id:
        await message.answer("❌ Не удалось определить пользователя.", reply_markup=get_admin_main_kb(is_chief=True))
        await state.finish()
        return

    # Проверяем, не админ ли уже
    if user_id in CHIEF_ADMIN_IDS or await db.is_admin(user_id):
        await message.answer("Этот пользователь уже является админом.", reply_markup=get_admin_main_kb(is_chief=True))
        await state.finish()
        return

    ok = await db.add_admin(
        user_id=user_id, username=username, added_by=message.from_user.id, role="junior"
    )
    await state.finish()
    if ok:
        await message.answer(
            f"✅ Администратор добавлен:\nID: <code>{user_id}</code> | @{username or '-'}",
            reply_markup=get_admin_main_kb(is_chief=True),
        )
    else:
        await message.answer("❌ Не удалось добавить администратора.", reply_markup=get_admin_main_kb(is_chief=True))


# ---------------- удаление админа по ID ----------------

@dp.callback_query_handler(lambda c: c.data == "admin_delete")
async def admin_delete_start(call: types.CallbackQuery, state: FSMContext):
    is_chief = call.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await call.answer("⛔ Только для главного администратора", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_admin_delete_id)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")]]
    )
    await call.message.answer(
        "Введите ID админа, которого удалить:",
        reply_markup=cancel_kb,
    )
    await call.answer()


@dp.message_handler(state=AdminStates.waiting_admin_delete_id)
async def admin_delete_user_id(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=True))
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно целое число. Попробуйте ещё:")
        return

    if user_id in CHIEF_ADMIN_IDS:
        await message.answer("Нельзя удалить главного администратора.", reply_markup=get_admin_main_kb(is_chief=True))
        await state.finish()
        return

    ok = await db.remove_admin(user_id)
    await state.finish()
    if ok:
        await message.answer(f"✅ Администратор {user_id} удалён.", reply_markup=get_admin_main_kb(is_chief=True))
    else:
        await message.answer("❌ Администратор не найден или уже удалён.", reply_markup=get_admin_main_kb(is_chief=True))


# ---------------- заблокированные ----------------

@dp.message_handler(lambda m: m.text == "🚫 Заблокированные")
async def admin_blocked_list(message: types.Message):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)

    if not is_admin:
        return
    blocked = await db.get_blocked_users()
    if not blocked:
        await message.answer("Нет заблокированных пользователей.", reply_markup=get_back_kb())
        return
    text = "🚫 <b>Заблокированные пользователи:</b>\n\n"
    for b in blocked:
        text += f"• ID: <code>{b['user_id']}</code> | заблокирован: {b['blocked_at'][:16]}\n"
    await message.answer(text, reply_markup=get_back_kb())


# ---------------- расписание ----------------

@dp.message_handler(lambda m: m.text == "📅 Отправить расписание")
async def admin_schedule_start(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)

    if not is_admin:
        return

    if not SCHEDULE_CHANNEL_ID:
        await message.answer(
            "❌ Канал для расписания не настроен. Укажите SCHEDULE_CHANNEL_ID в переменных окружения.",
            reply_markup=get_admin_main_kb(is_chief=is_chief),
        )
        return

    # Проверка кдауна (не для chief)
    if not is_chief:
        last = await db.get_last_schedule_post()
        cooldown_hours = int(await db.get_setting("schedule_cooldown_hours") or SCHEDULE_COOLDOWN_HOURS)
        if last:
            next_allowed = datetime.fromisoformat(last["next_allowed_at"])
            if datetime.utcnow() < next_allowed:
                wait = next_allowed - datetime.utcnow()
                minutes = int(wait.total_seconds() // 60)
                await message.answer(
                    f"⏳ Расписание можно отправлять не чаще раза в {cooldown_hours} ч.\n"
                    f"Осталось подождать примерно {minutes} мин.",
                    reply_markup=get_admin_main_kb(is_chief=is_chief),
                )
                return

    await state.set_state(ScheduleStates.waiting_photo)
    await message.answer("Пришлите фото расписания:")


@dp.message_handler(content_types=['photo'], state=ScheduleStates.waiting_photo)
async def admin_schedule_photo(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)

    if not is_admin:
        return

    if not SCHEDULE_CHANNEL_ID:
        await message.answer(
            "❌ Канал для расписания не настроен. Укажите SCHEDULE_CHANNEL_ID в переменных окружения.",
            reply_markup=get_admin_main_kb(is_chief=is_chief),
        )
        await state.finish()
        return

    file_id = message.photo[-1].file_id
    caption = message.caption or None

    # Формируем текст с хештегом, календарём и датой (завтра, без года)
    tomorrow = datetime.utcnow() + timedelta(days=1)
    date_str = tomorrow.strftime("%d.%m")
    if caption:
        full_caption = f"#Расписание 📅 {date_str}\n\n{caption}"
    else:
        full_caption = f"#Расписание 📅 {date_str}"

    # Проверка кдауна ещё перед отправкой (защита от гонки)
    if not is_chief:
        last = await db.get_last_schedule_post()
        cooldown_hours = int(await db.get_setting("schedule_cooldown_hours") or SCHEDULE_COOLDOWN_HOURS)
        if last:
            next_allowed = datetime.fromisoformat(last["next_allowed_at"])
            if datetime.utcnow() < next_allowed:
                await message.answer("⏳ К сожалению, пока нельзя отправить расписание (кдаун).")
                await state.finish()
                return

    # Отправляем в канал
    try:
        await bot.send_photo(SCHEDULE_CHANNEL_ID, file_id, caption=full_caption)
    except Exception as e:
        logger.exception("Не удалось отправить фото в канал расписания")
        await message.answer(
            f"❌ Не удалось отправить в канал: {e}\n"
            "Убедитесь, что бот является администратором канала с правом «Отправлять сообщения».",
            reply_markup=get_admin_main_kb(is_chief=is_chief),
        )
        await state.finish()
        return

    # Сохраняем пост
    next_allowed = datetime.utcnow() + timedelta(hours=SCHEDULE_COOLDOWN_HOURS)
    await db.add_schedule_post(
        file_id=file_id,
        caption=caption,
        posted_by=message.from_user.id,
        next_allowed_at=next_allowed.isoformat(),
    )

    await state.finish()
    await message.answer("✅ Расписание отправлено в канал.", reply_markup=get_admin_main_kb(is_chief=is_chief))

    # Уведомляем всех chief админов, если отправил junior
    if not is_chief:
        for chief_id in CHIEF_ADMIN_IDS:
            try:
                await bot.send_message(
                    chief_id,
                    f"📅 Расписание отправил младший администратор @{message.from_user.username or 'без ника'}",
                )
            except Exception:
                logger.exception("Не удалось уведомить chief %s о расписании", chief_id)


@dp.message_handler(state=ScheduleStates.waiting_photo)
async def admin_schedule_wrong_content(message: types.Message, state: FSMContext):
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=is_chief))
        return
    await message.answer("Пришлите, пожалуйста, именно фото расписания.")


# ---------------- навигация ----------------

@dp.callback_query_handler(lambda c: c.data == "admin_back")
async def admin_back_cb(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.edit_message_text(
        "🔐 Админ-панель",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=get_admin_main_kb(is_chief=call.from_user.id in CHIEF_ADMIN_IDS),
    )
    await call.answer()


# ---------------- технические работы (только chief) ----------------

@dp.message_handler(lambda m: m.text == "🔧 Технические работы")
async def admin_maintenance_toggle(message: types.Message):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await message.answer(
            "⛔ Только для главного администратора",
            reply_markup=get_admin_main_kb(is_chief=False),
        )
        return

    current = await db.get_maintenance_mode()
    new_mode = not current
    await db.set_maintenance_mode(new_mode)

    status = "включён" if new_mode else "выключен"
    user_msg = (
        "Пользователи не могут отправлять анонимные сообщения."
        if new_mode
        else "Бот работает в обычном режиме."
    )
    await message.answer(
        f"🔧 Технические работы {status}.\n{user_msg}",
        reply_markup=get_admin_main_kb(is_chief=True),
    )


# ---------------- добавление школьного мероприятия (только chief) ----------------

@dp.message_handler(lambda m: m.text == "🏫 Добавить мероприятие")
async def admin_add_event_start(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await message.answer(
            "⛔ Только для главного администратора",
            reply_markup=get_admin_main_kb(is_chief=False),
        )
        return

    await state.set_state(AdminStates.waiting_event_title)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")]]
    )
    await message.answer(
        "📝 Введите <b>название</b> школьного мероприятия:\n\n"
        "Нажмите «❌ Отмена», чтобы выйти.",
        reply_markup=cancel_kb,
    )


@dp.message_handler(state=AdminStates.waiting_event_title)
async def admin_event_title(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=True))
        return

    await state.update_data(event_title=message.text.strip())
    await state.set_state(AdminStates.waiting_event_desc)
    await message.answer(
        "📝 Введите <b>описание</b> мероприятия:\n\n"
        "Нажмите «❌ Отмена», чтобы выйти.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")]]
        ),
    )


@dp.message_handler(state=AdminStates.waiting_event_desc)
async def admin_event_desc(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=True))
        return

    await state.update_data(event_desc=message.text.strip() or None)
    await state.set_state(AdminStates.waiting_event_date)
    await message.answer(
        "📅 Введите <b>дату</b> мероприятия (например: 01.09.2026):\n\n"
        "Нажмите «❌ Отмена», чтобы выйти.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")]]
        ),
    )


@dp.message_handler(state=AdminStates.waiting_event_date)
async def admin_event_date(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=True))
        return

    event_date = message.text.strip()
    await state.update_data(event_date=event_date)
    await state.set_state(AdminStates.waiting_event_photo)

    skip_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить фото", callback_data="event_skip_photo")],
            [InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")],
        ]
    )
    await message.answer(
        "🖼 Пришлите <b>фото</b> мероприятия или нажмите «Пропустить фото\":\n\n"
        "Нажмите «❌ Отмена», чтобы выйти.",
        reply_markup=skip_kb,
    )


@dp.callback_query_handler(lambda c: c.data == "event_skip_photo", state=AdminStates.waiting_event_photo)
async def event_skip_photo_cb(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    title = data.get("event_title")
    desc = data.get("event_desc")
    event_date = data.get("event_date")

    await db.add_school_event(
        title=title,
        description=desc,
        event_date=event_date,
        created_by=call.from_user.id,
        photo_id=None,
    )
    await state.finish()

    await call.message.edit_text(
        f"✅ Мероприятие добавлено:\n"
        f"<b>{title}</b>\n📅 {event_date}\n📝 {desc or '—'}\n🖼 Фото: без фото",
    )
    await call.message.answer(
        "Готово!",
        reply_markup=get_admin_main_kb(is_chief=True),
    )
    await call.answer()


@dp.message_handler(content_types=["photo"], state=AdminStates.waiting_event_photo)
async def admin_event_photo(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    title = data.get("event_title")
    desc = data.get("event_desc")
    event_date = data.get("event_date")

    await db.add_school_event(
        title=title,
        description=desc,
        event_date=event_date,
        created_by=message.from_user.id,
        photo_id=photo_id,
    )
    await state.finish()

    await message.answer_photo(
        photo_id,
        caption=(
            f"✅ Мероприятие добавлено:\n"
            f"<b>{title}</b>\n📅 {event_date}\n📝 {desc or '—'}"
        ),
    )
    await message.answer("Готово!", reply_markup=get_admin_main_kb(is_chief=True))


# ---------------- рассылка важного объявления (только chief) ----------------

@dp.message_handler(lambda m: m.text == "📢 Рассылка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await message.answer(
            "⛔ Только для главного администратора",
            reply_markup=get_admin_main_kb(is_chief=False),
        )
        return

    await state.set_state(AdminStates.waiting_broadcast_text)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="fsm_cancel")]]
    )
    await message.answer(
        "📝 Введите текст важного объявления для рассылки:\n\n"
        "Сообщение будет отправлено в канал и всем пользователям бота с префиксом ❗ВАЖНО❗.\n\n"
        "Нажмите «❌ Отмена», чтобы выйти.",
        reply_markup=cancel_kb,
    )


@dp.message_handler(state=AdminStates.waiting_broadcast_text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    if message.text and message.text.strip() == CANCEL_TEXT:
        await state.finish()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_main_kb(is_chief=True))
        return

    text = message.text.strip()
    prefix = "❗ВАЖНО❗\n\n"

    sent_to_channel = False
    channel_message_id = None
    sent_to_users = 0
    failed_users = 0

    # Рассылка в канал
    if SCHEDULE_CHANNEL_ID:
        try:
            sent = await bot.send_message(SCHEDULE_CHANNEL_ID, prefix + text)
            sent_to_channel = True
            channel_message_id = sent.message_id
        except Exception:
            logger.exception("Не удалось отправить рассылку в канал")

    # Рассылка пользователям
    users = await db.get_all_users()
    for user_id in users:
        if user_id == message.from_user.id:
            continue
        try:
            await bot.send_message(user_id, prefix + text)
            sent_to_users += 1
        except Exception:
            failed_users += 1

    # Сохраняем рассылку в БД
    await db.add_broadcast(
        text=text,
        prefix=prefix,
        sent_by=message.from_user.id,
        sent_to_channel=sent_to_channel,
        channel_message_id=channel_message_id,
    )

    await state.finish()

    report = f"📢 Рассылка завершена:\n"
    if sent_to_channel:
        report += f"✅ В канал: отправлено\n"
    else:
        report += f"❌ В канал: ошибка\n"
    report += f"✅ Пользователям: {sent_to_users}\n"
    if failed_users:
        report += f"❌ Не доставлено: {failed_users}"

    await message.answer(report, reply_markup=get_admin_main_kb(is_chief=True))


# ---------------- удаление школьного мероприятия (только chief) ----------------

@dp.message_handler(lambda m: m.text == "🗑 Удалить мероприятие")
async def admin_delete_event_start(message: types.Message):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await message.answer(
            "⛔ Только для главного администратора",
            reply_markup=get_admin_main_kb(is_chief=False),
        )
        return

    events = await db.get_active_school_events()
    if not events:
        await message.answer(
            "📅 Нет активных мероприятий для удаления.",
            reply_markup=get_admin_main_kb(is_chief=True),
        )
        return

    kb_buttons = []
    for e in events:
        kb_buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {e['title']} ({e['event_date']})",
                callback_data=f"delete_event:{e['id']}",
            )
        ])
    kb_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(
        "🗑 Выберите мероприятие для удаления:",
        reply_markup=kb,
    )


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("delete_event:"))
async def admin_delete_event_cb(call: types.CallbackQuery):
    db: Database = call.bot.db  # type: ignore
    is_chief = call.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await call.answer("⛔ Только для главного администратора", show_alert=True)
        return

    event_id = int(call.data.split(":")[1])

    ok = await db.delete_school_event(event_id)
    if ok:
        await call.answer("✅ Мероприятие удалено")
        await call.message.edit_text(
            "✅ Мероприятие удалено из списка.",
            reply_markup=None,
        )
    else:
        await call.answer("❌ Не удалось удалить мероприятие", show_alert=True)


# ---------------- история и удаление рассылок (только chief) ----------------

@dp.message_handler(lambda m: m.text == "📜 История рассылок")
async def admin_broadcast_history(message: types.Message):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await message.answer(
            "⛔ Только для главного администратора",
            reply_markup=get_admin_main_kb(is_chief=False),
        )
        return

    broadcasts = await db.get_broadcasts(limit=10)
    if not broadcasts:
        await message.answer(
            "📜 Рассылок пока нет.",
            reply_markup=get_admin_main_kb(is_chief=True),
        )
        return

    text = "📜 <b>История рассылок:</b>\n\n"
    kb_buttons = []
    for b in broadcasts:
        date_str = b["sent_at"][:16].replace("T", " ")
        channel_mark = " 📢" if b["sent_to_channel"] else ""
        text += f"• <b>#{b['id']}</b> {date_str}{channel_mark}\n"
        text += f"  {b['text'][:50]}{'...' if len(b['text']) > 50 else ''}\n\n"
        kb_buttons.append([
            InlineKeyboardButton(
                text=f"🗑 Удалить #{b['id']}",
                callback_data=f"delete_broadcast:{b['id']}",
            )
        ])
    kb_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("delete_broadcast:"))
async def admin_delete_broadcast_cb(call: types.CallbackQuery):
    db: Database = call.bot.db  # type: ignore
    is_chief = call.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await call.answer("⛔ Только для главного администратора", show_alert=True)
        return

    broadcast_id = int(call.data.split(":")[1])

    broadcast = await db.get_broadcast(broadcast_id)
    if not broadcast:
        await call.answer("Рассылка не найдена", show_alert=True)
        return

    # Пытаемся удалить из канала, если было отправлено
    deleted_channel = False
    if broadcast["sent_to_channel"] and broadcast["channel_message_id"] and SCHEDULE_CHANNEL_ID:
        try:
            await bot.delete_message(
                SCHEDULE_CHANNEL_ID,
                broadcast["channel_message_id"],
            )
            deleted_channel = True
        except Exception:
            logger.exception("Не удалось удалить сообщение из канала")

    # Удаляем запись из БД
    ok = await db.delete_broadcast(broadcast_id)

    if ok:
        msg = "✅ Рассылка удалена из истории."
        if deleted_channel:
            msg += "\n✅ Сообщение удалено из канала."
        elif broadcast["sent_to_channel"]:
            msg += "\n⚠️ Не удалось удалить сообщение из канала (бот может не иметь прав)."
        await call.answer("✅ Удалено")
        await call.message.edit_text(msg, reply_markup=None)
    else:
        await call.answer("❌ Не удалось удалить рассылку", show_alert=True)
