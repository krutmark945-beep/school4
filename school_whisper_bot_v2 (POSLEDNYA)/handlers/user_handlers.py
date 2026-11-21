import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import ContentType, InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from config import CHIEF_ADMIN_ID, SCHEDULE_CHANNEL_ID, ALLOWED_CONTENT_TYPES
from database.db import Database
from keyboards.admin_kb import get_admin_main_kb

logger = logging.getLogger(__name__)


# ---------------- пользовательские хендлеры ----------------

@dp.message_handler(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, db: Database, is_admin: bool, is_chief: bool):
    # Регистрируем пользователя (просто убедимся, что он не заблокирован)
    if await db.is_blocked(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к боту.")
        return

    if is_admin:
        # Админу сразу показываем админ-панель
        role = "Главный администратор" if is_chief else "Младший администратор"
        await message.answer(
            f"👋 Добро пожаловать, администратор!\nВаша роль: {role}",
            reply_markup=get_admin_main_kb(),
        )
    else:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Отправьте анонимное сообщение (текст, фото или видео). "
            "Оно будет передано администраторам без вашего имени и ника."
        )


@dp.message_handler(content_types=[ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO])
async def anonymous_message(message: types.Message, db: Database):
    """Пользователь прислал анонимное сообщение."""
    if await db.is_blocked(message.from_user.id):
        return  # заблокирован — игнорируем молча

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

    # Сохраняем в БД
    msg_id = await db.add_anonymous_message(
        user_id=message.from_user.id,
        message_type=msg_type,
        file_id=file_id,
        text=text if text else None,
    )

    await message.answer("✅ Анонимное сообщение отправлено администраторам.")

    # Рассылаем всем админам с кнопками «Заблокировать» и «Выслать в канал»
    admins = await db.get_admins()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data=f"block_user:{msg_id}"),
                InlineKeyboardButton(text="📤 Выслать в канал", callback_data=f"forward_channel:{msg_id}"),
            ]
        ]
    )

    header = f"📨 Анонимное сообщение #{msg_id}\n\n"
    if text:
        header += f"📝 Текст:\n{text}\n\n"
    else:
        header += f"📎 Медиафайл (без текста)\n\n"

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
async def block_user_cb(call: types.CallbackQuery, db: Database, is_admin: bool):
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

    await call.answer("✅ Пользователь заблокирован")
    await bot.edit_message_text(
        call.message.text + "\n\n🚫 Пользователь заблокирован.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None,
    )


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("forward_channel:"))
async def forward_channel_cb(call: types.CallbackQuery, db: Database, is_admin: bool):
    """Пересылка анонимного сообщения в основной канал."""
    if not is_admin:
        await call.answer("⛔ Только для администраторов", show_alert=True)
        return

    message_id = int(call.data.split(":")[1])

    # Получаем инфо о сообщении
    async with db._connect() as conn:
        async with conn.execute(
            "SELECT user_id, message_type, file_id, text FROM anonymous_messages WHERE id = ?", (message_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        await call.answer("Сообщение не найдено", show_alert=True)
        return

    msg_type = row["message_type"]
    file_id = row["file_id"]
    text = row["text"] or ""
    user_id = row["user_id"]

    try:
        caption = f"📢 Анонимное сообщение #{message_id}\n\n{text}" if text else f"📢 Анонимное сообщение #{message_id}"

        if msg_type == "photo":
            await bot.send_photo(SCHEDULE_CHANNEL_ID, file_id, caption=caption)
        elif msg_type == "video":
            await bot.send_video(SCHEDULE_CHANNEL_ID, file_id, caption=caption)
        else:
            await bot.send_message(SCHEDULE_CHANNEL_ID, caption)

        await call.answer("✅ Отправлено в канал")
        await bot.edit_message_text(
            call.message.text + "\n\n📤 Выслано в канал.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
    except Exception:
        logger.exception("Не удалось отправить в канал")
        await call.answer("❌ Не удалось отправить в канал", show_alert=True)
