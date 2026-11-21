import logging
from datetime import datetime, timedelta
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from config import CHIEF_ADMIN_IDS, SCHEDULE_CHANNEL_ID, SCHEDULE_COOLDOWN_HOURS
from database.db import Database
from keyboards.admin_kb import get_admin_main_kb, get_back_kb

logger = logging.getLogger(__name__)


def _get_db(message: types.Message) -> Database:
    return message.bot.db  # type: ignore


# ---------------- FSM состояния ----------------

class AdminStates(StatesGroup):
    waiting_admin_add = State()       # ждём пересылку сообщения или username для добавления админа
    waiting_admin_delete_id = State() # ждём ID для удаления админа


class ScheduleStates(StatesGroup):
    waiting_photo = State()


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
        reply_markup=get_admin_main_kb(),
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
    if not admins:
        await message.answer("Админов не найдено.", reply_markup=get_back_kb())
        return

    text = "👥 <b>Список администраторов:</b>\n\n"
    for a in admins:
        role_emoji = "👑" if a["role"] == "chief" else "👤"
        text += f"{role_emoji} ID: <code>{a['user_id']}</code> | @{a['username'] or '-'} | {a['role']}\n"

    kb_buttons = []
    if is_chief:
        kb_buttons.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")])
        kb_buttons.append([InlineKeyboardButton(text="🗑 Удалить админа", callback_data="admin_delete")])
    kb_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb)


# ---------------- добавление админа через пересылку / username ----------------

@dp.callback_query_handler(lambda c: c.data == "admin_add")
async def admin_add_start(call: types.CallbackQuery, state: FSMContext):
    db: Database = call.bot.db  # type: ignore
    is_chief = call.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await call.answer("⛔ Только для главного администратора", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_admin_add)
    await call.message.answer(
        "📥 Перешлите любое сообщение от пользователя, которого хотите сделать админом,\n"
        "или пришлите его username (без @)."
    )
    await call.answer()


@dp.message_handler(state=AdminStates.waiting_admin_add)
async def admin_waiting_admin_add(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return

    user_id = None
    username = None

    # Способ 1: пересланное сообщение
    if message.forward_from:
        user_id = message.forward_from.id
        username = message.forward_from.username

    # Способ 2: username текстом
    elif message.text:
        raw = message.text.strip()
        if raw.startswith("@"):
            raw = raw[1:]
        try:
            chat = await bot.get_chat(raw)
            user_id = chat.id
            username = chat.username
        except Exception:
            await message.answer(
                "❌ Не удалось найти пользователя по username.\n"
                "Убедитесь, что пользователь начал диалог с ботом или перешлите его сообщение."
            )
            return
    else:
        await message.answer("Пришлите пересланное сообщение или username пользователя.")
        return

    if not user_id:
        await message.answer("❌ Не удалось определить пользователя.")
        await state.finish()
        return

    # Проверяем, не админ ли уже
    if await db.is_admin(user_id) or user_id in CHIEF_ADMIN_IDS:
        await message.answer("Этот пользователь уже является админом.")
        await state.finish()
        return

    ok = await db.add_admin(
        user_id=user_id, username=username, added_by=message.from_user.id, role="junior"
    )
    await state.finish()
    if ok:
        await message.answer(
            f"✅ Администратор добавлен:\nID: <code>{user_id}</code> | @{username or '-'}",
            reply_markup=get_admin_main_kb(),
        )
    else:
        await message.answer("❌ Не удалось добавить администратора.", reply_markup=get_admin_main_kb())


# ---------------- удаление админа по ID ----------------

@dp.callback_query_handler(lambda c: c.data == "admin_delete")
async def admin_delete_start(call: types.CallbackQuery, state: FSMContext):
    db: Database = call.bot.db  # type: ignore
    is_chief = call.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        await call.answer("⛔ Только для главного администратора", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_admin_delete_id)
    await call.message.answer("Введите ID админа, которого удалить:")
    await call.answer()


@dp.message_handler(state=AdminStates.waiting_admin_delete_id)
async def admin_delete_user_id(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)
    is_chief = message.from_user.id in CHIEF_ADMIN_IDS

    if not is_chief:
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно целое число. Попробуйте ещё:")
        return

    if user_id in CHIEF_ADMIN_IDS:
        await message.answer("Нельзя удалить главного администратора.")
        await state.finish()
        return

    ok = await db.remove_admin(user_id)
    await state.finish()
    if ok:
        await message.answer(f"✅ Администратор {user_id} удалён.", reply_markup=get_admin_main_kb())
    else:
        await message.answer("❌ Администратор не найден или уже удалён.", reply_markup=get_admin_main_kb())


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
                    reply_markup=get_admin_main_kb(),
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

    file_id = message.photo[-1].file_id
    caption = message.caption or None

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
        await bot.send_photo(SCHEDULE_CHANNEL_ID, file_id, caption=caption)
    except Exception:
        logger.exception("Не удалось отправить фото в канал расписания")
        await message.answer("❌ Не удалось отправить в канал. Проверьте права бота в канале.")
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
    await message.answer("✅ Расписание отправлено в канал.", reply_markup=get_admin_main_kb())

    # Уведомляем всех chief админов, если отправил junior
    if not is_chief:
        for chief_id in CHIEF_ADMIN_IDS:
            try:
                await bot.send_message(
                    chief_id,
                    f"📅 Расписание отправлено младшим администратором ID: <code>{message.from_user.id}</code>\n"
                    f"@{message.from_user.username or '-'}\n"
                    f"Канал: <code>{SCHEDULE_CHANNEL_ID}</code>",
                )
            except Exception:
                logger.exception("Не удалось уведомить chief %s о расписании", chief_id)


@dp.message_handler(state=ScheduleStates.waiting_photo)
async def admin_schedule_wrong_content(message: types.Message):
    await message.answer("Пришлите, пожалуйста, именно фото расписания.")


# ---------------- навигация ----------------

@dp.callback_query_handler(lambda c: c.data == "admin_back")
async def admin_back_cb(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.edit_message_text(
        "🔐 Админ-панель",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=get_admin_main_kb(),
    )
    await call.answer()
