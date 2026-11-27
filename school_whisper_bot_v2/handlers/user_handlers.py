import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from config import (
    CHIEF_ADMIN_IDS,
    SCHEDULE_CHANNEL_ID,
    ALLOWED_CONTENT_TYPES,
    RULES_LINK,
    contains_profanity,
)
from database.db import Database
from keyboards.admin_kb import get_admin_main_kb
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

logger = logging.getLogger(__name__)


# ---------------- состояния для ответа пользователю ----------------

class ReplyStates(StatesGroup):
    waiting_reply = State()               # админ пишет ответ пользователю
    waiting_reply_from_user = State()     # пользователь пишет ответ администратору


def _get_db(message: types.Message) -> Database:
    return message.bot.db  # type: ignore


# ---------------- пользовательские хендлеры ----------------

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    db: Database = _get_db(message)

    # Регистрируем пользователя (просто убедимся, что он не заблокирован)
    if await db.is_blocked(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к боту.")
        return

    # Сохраняем пользователя для рассылки
    await db.add_or_update_user(message.from_user.id, message.from_user.username)

    # Проверяем, принял ли пользователь правила. Если нет — показываем правила и кнопку «Я прочитал».
    if not await db.has_accepted_rules(message.from_user.id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Я прочитал", callback_data="rules_accept")]
            ]
        )
        await message.answer(
            "⚠️ Перед началом работы обязательно прочтите правила:\n"
            f"{RULES_LINK}\n\n"
            "Нажмите кнопку «✅ Я прочитал», чтобы продолжить пользоваться ботом.",
            reply_markup=kb,
        )
        return

    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)

    if is_admin:
        # Админу сразу показываем админ-панель
        role = "Главный администратор" if is_chief else "Младший администратор"
        await message.answer(
            f"👋 Добро пожаловать, администратор!\nВаша роль: {role}",
            reply_markup=get_admin_main_kb(is_chief=is_chief),
        )
    else:
        # Обычный пользователь — показываем кнопку школьных мероприятий
        user_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏫 Школьные мероприятия")]],
            resize_keyboard=True,
        )
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Отправьте анонимное сообщение (текст, фото или видео). "
            "Оно будет передано администраторам без вашего имени и ника.\n\n"
            "Также вы можете посмотреть школьные мероприятия ниже 👇",
            reply_markup=user_kb,
        )


@dp.callback_query_handler(lambda c: c.data == "rules_accept")
async def rules_accept_cb(call: types.CallbackQuery):
    db: Database = call.bot.db  # type: ignore

    await db.accept_rules(call.from_user.id)
    await call.answer("✅ Правила приняты")

    await bot.edit_message_text(
        "✅ Вы приняли правила. Теперь вы можете отправлять анонимные сообщения.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
    )
    await call.message.answer(
        "👋 Добро пожаловать!\n\n"
        "Отправьте анонимное сообщение (текст, фото или видео). "
        "Оно будет передано администраторам без вашего имени и ника."
    )


ADMIN_BUTTONS = {
    "👥 Младшие админы",
    "🚫 Заблокированные",
    "📅 Отправить расписание",
    "🔙 Назад",
    "🔐 Админ-панель",
}


# ---------------- кнопка «Назад» (исправление бага) ----------------

@dp.message_handler(lambda m: m.text == "🔙 Назад")
async def admin_back_button(message: types.Message):
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


# ---------------- кнопка «🔐 Админ-панель» (reply-кнопка) ----------------

@dp.message_handler(lambda m: m.text == "🔐 Админ-панель")
async def admin_panel_button(message: types.Message):
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


# ---------------- школьные мероприятия (обычные пользователи) ----------------

@dp.message_handler(lambda m: m.text == "🏫 Школьные мероприятия")
async def school_events_button(message: types.Message):
    db: Database = _get_db(message)

    if await db.is_blocked(message.from_user.id):
        return

    if not await db.has_accepted_rules(message.from_user.id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✅ Я прочитал", callback_data="rules_accept")]]
        )
        await message.answer(
            "⚠️ Перед началом работы обязательно прочтите правила:\n"
            f"{RULES_LINK}\n\n"
            "Нажмите кнопку «✅ Я прочитал», чтобы продолжить пользоваться ботом.",
            reply_markup=kb,
        )
        return

    events = await db.get_active_school_events()
    if not events:
        await message.answer("📅 Сейчас нет запланированных школьных мероприятий.")
        return

    text = "📅 <b>Школьные мероприятия:</b>\n\n"
    for e in events:
        text += f"• <b>{e['title']}</b>\n📅 {e['event_date']}\n📝 {e['description'] or '—'}\n\n"

    # Показываем фото первого мероприятия, если оно есть, иначе просто текст
    first_event = events[0]
    if first_event["photo_id"]:
        await bot.send_photo(
            message.from_user.id,
            first_event["photo_id"],
            caption=text,
        )
    else:
        await message.answer(text)


@dp.message_handler(content_types=['text', 'photo', 'video'])
async def anonymous_message(message: types.Message):
    db: Database = _get_db(message)

    # Не обрабатываем как анонимное сообщение, если пользователь в состоянии ответа админу
    state = dp.current_state(chat=message.from_user.id, user=message.from_user.id)
    current_state = await state.get_state()
    if current_state in (
        ReplyStates.waiting_reply_from_user.state,
        ReplyStates.waiting_reply.state,
    ):
        return

    # Если это админская кнопка — не обрабатываем как анонимное сообщение
    if message.content_type == "text" and message.text in ADMIN_BUTTONS:
        return

    if await db.is_blocked(message.from_user.id):
        return  # заблокирован — игнорируем молча

    is_chief = message.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(message.from_user.id)
    is_junior_admin = bool(is_admin and not is_chief)

    # Сохраняем пользователя для рассылки
    await db.add_or_update_user(message.from_user.id, message.from_user.username)

    # Технические работы: блокируем анонки для не-админов
    if await db.get_maintenance_mode() and not is_admin:
        await message.answer(
            "⚠️ Бот находится на технических работах. "
            "Попробуйте написать позже."
        )
        return

    # Проверяем, принял ли пользователь правила. Если нет — показываем кнопку «Я прочитал».
    if not await db.has_accepted_rules(message.from_user.id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Я прочитал", callback_data="rules_accept")]
            ]
        )
        await message.answer(
            "⚠️ Перед началом работы обязательно прочтите правила:\n"
            f"{RULES_LINK}\n\n"
            "Нажмите кнопку «✅ Я прочитал», чтобы продолжить пользоваться ботом.",
            reply_markup=kb,
        )
        return

    # Определяем тип контента и текст
    if message.content_type == "text":
        msg_type = "text"
        file_id = None
        text = message.text or ""
    elif message.content_type == "photo":
        msg_type = "photo"
        file_id = message.photo[-1].file_id
        text = message.caption or ""
    elif message.content_type == "video":
        msg_type = "video"
        file_id = message.video.file_id
        text = message.caption or ""
    else:
        await message.answer("❌ Поддерживаются только текст, фото и видео.")
        return

    # Фильтр нецензурной лексики
    bad_word = contains_profanity(text or "")

    if bad_word and not is_chief:
        # Сохраняем сообщение с пометкой о запретном слове
        msg_id = await db.add_anonymous_message(
            user_id=message.from_user.id,
            message_type=msg_type,
            file_id=file_id,
            text=text if text else None,
            filtered_word=bad_word,
        )

        # Уведомляем пользователя
        await message.answer(
            f"❌ Ваше сообщение не будет допущено к публикации.\n"
            f"Причина: обнаружено запрещённое слово *{bad_word}*."
        )

        # Рассылаем младшим админам (и chief тоже для информирования)
        admins = await db.get_admins()
        for admin in admins:
            if admin["role"] not in ("junior", "chief"):
                continue
            try:
                admin_text = (
                    f"⚠️ Анонимное сообщение #{msg_id} не прошло фильтр мата.\n"
                    f"Запрещённое слово: *{bad_word}*\n\n"
                )
                if text:
                    admin_text += f"📝 Текст:\n{text}\n\n"
                else:
                    admin_text += f"📎 Медиафайл (без текста)\n\n"
                admin_text += "❌ Публиковать в канал запрещено."

                if msg_type == "photo":
                    await bot.send_photo(admin["user_id"], file_id, caption=admin_text)
                elif msg_type == "video":
                    await bot.send_video(admin["user_id"], file_id, caption=admin_text)
                else:
                    await bot.send_message(admin["user_id"], admin_text)
            except Exception:
                logger.exception("Не удалось отправить сообщение с матом админу %s", admin["user_id"])

        return

    # Для chief не фильтруем мат
    if is_chief:
        bad_word = None

    # Сохраняем в БД (отмечаем слово, вызвавшее срабатывание фильтра, если такое есть)
    msg_id = await db.add_anonymous_message(
        user_id=message.from_user.id,
        message_type=msg_type,
        file_id=file_id,
        text=text if text else None,
        filtered_word=bad_word,
    )

    # Кнопки для админов — кнопка в канал выделена крупно
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data=f"block_user:{msg_id}"),
            ],
            [
                InlineKeyboardButton(text="📤 ВЫСЛАТЬ В КАНАЛ", callback_data=f"forward_channel:{msg_id}"),
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить сообщение", callback_data=f"delete_message:{msg_id}"),
                InlineKeyboardButton(text="✉️ Ответить пользователю", callback_data=f"reply_user:{msg_id}"),
            ]
        ]
    )

    header = f"📨 Анонимное сообщение #{msg_id}\n\n"
    if text:
        header += f"📝 Текст:\n{text}\n\n"
    else:
        header += f"📎 Медиафайл (без текста)\n\n"

    if bad_word:
        # Предупреждение о запрещённых словах
        profanity_note = f"⚠️ Внимание: сообщение содержит запрещённые слова: *{bad_word}*\n❌ Публиковать в канал запрещено.\n\n"

        # Рассылаем всем админам: chief получает полное сообщение с предупреждением,
        # junior — уведомление о блокировке публикации
        admins = await db.get_admins()
        for admin in admins:
            try:
                if admin["role"] == "chief":
                    chief_header = profanity_note + header
                    if msg_type == "photo":
                        await bot.send_photo(admin["user_id"], file_id, caption=chief_header)
                    elif msg_type == "video":
                        await bot.send_video(admin["user_id"], file_id, caption=chief_header)
                    else:
                        await bot.send_message(admin["user_id"], chief_header)
                else:
                    await bot.send_message(
                        admin["user_id"],
                        f"❌ Анонимное сообщение #{msg_id} не допущено фильтром из-за слова: *{bad_word}*.\n"
                        f"Публиковать в канал запрещено.",
                    )
            except Exception:
                logger.exception("Не удалось отправить сообщение админу %s", admin["user_id"])

        if is_junior_admin:
            await message.answer(
                f"❌ Сообщение не допущено фильтром из-за слова: *{bad_word}*.\n"
                f"Публиковать в канал запрещено."
            )
        else:
            await message.answer(
                "✅ Сообщение с предупреждением передано главным администраторам."
            )
        return

    # Обычная рассылка всем админам (мат не найден)
    await message.answer("✅ Анонимное сообщение отправлено администраторам.")

    admins = await db.get_admins()
    for admin in admins:
        try:
            if msg_type == "photo":
                await bot.send_photo(admin["user_id"], file_id, caption=header, reply_markup=kb)
            elif msg_type == "video":
                await bot.send_video(admin["user_id"], file_id, caption=header, reply_markup=kb)
            else:
                await bot.send_message(admin["user_id"], header, reply_markup=kb)
        except Exception:
            logger.exception("Не удалось отправить сообщение админу %s", admin["user_id"])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("block_user:"))
async def block_user_cb(call: types.CallbackQuery):
    db: Database = call.bot.db  # type: ignore

    is_chief = call.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(call.from_user.id)

    if not is_admin:
        await call.answer("⛔ Только для администраторов", show_alert=True)
        return

    message_id = int(call.data.split(":")[1])

    # Получаем инфо о сообщении, чтобы узнать user_id
    async with db._connect() as conn:
        async with conn.execute(
            "SELECT user_id, text, file_id FROM anonymous_messages WHERE id = ?", (message_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        await call.answer("Сообщение не найдено", show_alert=True)
        return

    user_id = row["user_id"]

    # Блокируем пользователя и помечаем сообщение
    await db.block_user(user_id, blocked_by=call.from_user.id, reason="Анонимное сообщение")
    await db.mark_message_blocked(message_id)

    # Уведомляем самого пользователя о блокировке
    try:
        await bot.send_message(
            user_id,
            "⛔ Вы были заблокированы администратором и больше не можете пользоваться ботом.",
        )
    except Exception:
        logger.exception("Не удалось уведомить пользователя %s о блокировке", user_id)

    await call.answer("✅ Пользователь заблокирован")
    await bot.edit_message_text(
        call.message.text + "\n\n🚫 Пользователь заблокирован.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("forward_channel:"))
async def forward_channel_cb(call: types.CallbackQuery):
    db: Database = call.bot.db  # type: ignore

    is_chief = call.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(call.from_user.id)

    if not is_admin:
        await call.answer("⛔ Только для администраторов", show_alert=True)
        return

    message_id = int(call.data.split(":")[1])

    # Получаем инфо о сообщении
    async with db._connect() as conn:
        async with conn.execute(
            "SELECT user_id, message_type, file_id, text, filtered_word FROM anonymous_messages WHERE id = ?", (message_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        await call.answer("Сообщение не найдено", show_alert=True)
        return

    msg_type = row["message_type"]
    file_id = row["file_id"]
    text = row["text"] or ""
    user_id = row["user_id"]
    filtered_word = row["filtered_word"]

    # Проверяем, не содержит ли сообщение запрещённые слова
    if filtered_word:
        await call.answer(
            f"❌ Это сообщение содержит запрещённое слово (*{filtered_word}*) и не может быть опубликовано в канале.",
            show_alert=True,
        )
        return

    # Проверяем, не отправляли ли уже это сообщение в канал
    if await db.is_message_forwarded(message_id):
        await call.answer("❌ Это сообщение уже было отправлено в канал.", show_alert=True)
        return

    # Проверяем, не удалено ли сообщение
    if await db.is_message_deleted(message_id):
        await call.answer("❌ Это сообщение было удалено администратором.", show_alert=True)
        return

    if not SCHEDULE_CHANNEL_ID:
        logger.error("SCHEDULE_CHANNEL_ID не задан в переменных окружения")
        await call.answer(
            "❌ Канал для рассылки не настроен. Обратитесь к главному администратору.",
            show_alert=True,
        )
        return

    try:
        # Только чистый текст анонки, без префиксов
        caption = text if text else ""

        if msg_type == "photo":
            await bot.send_photo(SCHEDULE_CHANNEL_ID, file_id, caption=caption)
        elif msg_type == "video":
            await bot.send_video(SCHEDULE_CHANNEL_ID, file_id, caption=caption)
        else:
            await bot.send_message(SCHEDULE_CHANNEL_ID, caption)

        await call.answer("✅ Отправлено в канал")
        await db.mark_message_forwarded(message_id)
        await bot.edit_message_text(
            call.message.text + "\n\n📤 Выслано в канал.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )

        # Уведомляем главных админов, кто из мл. админов отправил сообщение в канал
        for chief_id in CHIEF_ADMIN_IDS:
            try:
                await bot.send_message(
                    chief_id,
                    f"📤 Анонимное сообщение #{msg_id} отправлено в канал "
                    f"младшим администратором @{call.from_user.username or 'без ника'} "
                    f"(ID: <code>{call.from_user.id}</code>).",
                )
            except Exception:
                logger.exception("Не удалось уведомить chief %s о отправке в канал", chief_id)
    except Exception as e:
        logger.exception("Не удалось отправить в канал: %s", e)
        await call.answer(
            f"❌ Ошибка отправки: {e}\nПроверьте права бота в канале.",
            show_alert=True,
        )


# ---------------- удаление анонимного сообщения (не блокирует пользователя) ----------------

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("delete_message:"))
async def delete_message_cb(call: types.CallbackQuery):
    db: Database = call.bot.db  # type: ignore

    is_chief = call.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(call.from_user.id)

    if not is_admin:
        await call.answer("⛔ Только для администраторов", show_alert=True)
        return

    message_id = int(call.data.split(":")[1])

    if await db.is_message_deleted(message_id):
        await call.answer("Сообщение уже удалено.", show_alert=True)
        return

    await db.mark_message_deleted(message_id)

    await call.answer("✅ Сообщение удалено.")
    await bot.edit_message_text(
        call.message.text + "\n\n🗑 Сообщение удалено администратором.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )


# ---------------- ответ пользователю на анонимное сообщение ----------------

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("reply_user:"))
async def reply_user_cb(call: types.CallbackQuery, state: FSMContext):
    db: Database = call.bot.db  # type: ignore

    is_chief = call.from_user.id in CHIEF_ADMIN_IDS
    is_admin = is_chief or await db.is_admin(call.from_user.id)

    if not is_admin:
        await call.answer("⛔ Только для администраторов", show_alert=True)
        return

    message_id = int(call.data.split(":")[1])

    # Узнаём user_id оригинального автора
    async with db._connect() as conn:
        async with conn.execute(
            "SELECT user_id FROM anonymous_messages WHERE id = ?", (message_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        await call.answer("Сообщение не найдено", show_alert=True)
        return

    target_user_id = row["user_id"]

    await state.set_state(ReplyStates.waiting_reply)
    await state.update_data(
        target_user_id=target_user_id,
        admin_id=call.from_user.id,
        original_anon_id=message_id,
    )

    await call.message.answer(
        f"Введите текст ответа пользователю ID <code>{target_user_id}</code>:\n\n"
        "Напишите сообщение, и оно будет передано ему от имени администратора."
    )
    await call.answer()


@dp.message_handler(state=ReplyStates.waiting_reply)
async def send_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    original_anon_id = data.get("original_anon_id")
    admin_id = data.get("admin_id")
    await state.finish()

    if not target_user_id:
        await message.answer("❌ Ошибка: не определен получатель.")
        return

    try:
        sent = await bot.send_message(
            target_user_id,
            f"📨 Ответ от администратора на ваше анонимное сообщение #{original_anon_id or '?'}\n\n{message.text}",
        )

        # Даем возможность пользователю ответить на этот ответ
        user_state = dp.current_state(chat=target_user_id, user=target_user_id)
        await user_state.set_state(ReplyStates.waiting_reply_from_user)
        await user_state.update_data(
            admin_id=admin_id,
            original_anon_id=original_anon_id,
        )

        await message.answer("✅ Ответ отправлен пользователю.")
    except Exception:
        logger.exception("Не удалось отправить ответ пользователю %s", target_user_id)
        await message.answer("❌ Не удалось отправить ответ пользователю.")


# ---------------- ответ пользователя на сообщение администратора ----------------

@dp.message_handler(state=ReplyStates.waiting_reply_from_user)
async def user_reply_to_admin(message: types.Message, state: FSMContext):
    if message.content_type != "text":
        await message.answer("Пожалуйста, отправьте текстовый ответ.")
        return

    data = await state.get_data()
    admin_id = data.get("admin_id")
    original_anon_id = data.get("original_anon_id")
    await state.finish()

    if not admin_id:
        await message.answer("❌ Ошибка: не определен администратор.")
        return

    try:
        await bot.send_message(
            admin_id,
            f"📨 Ответ от пользователя на ваше сообщение в анонке #{original_anon_id or '?'}\n\n{message.text}",
        )
        await message.answer("✅ Ваш ответ отправлен администратору.")
    except Exception:
        logger.exception("Не удалось отправить ответ администратору %s", admin_id)
        await message.answer("❌ Не удалось отправить ответ.")
