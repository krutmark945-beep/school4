import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, DB_PATH, LOG_LEVEL, CHIEF_ADMIN_ID, SCHEDULE_CHANNEL_ID
from database.db import Database
from handlers.user_handlers import router as user_router
from handlers.admin_handlers import router as admin_router
from middlewares.admin_middleware import AdminMiddleware
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging(LOG_LEVEL)
    logger.info("Запуск бота...")

    # Проверка обязательных переменных
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not CHIEF_ADMIN_ID:
        missing.append("CHIEF_ADMIN_ID")
    if not SCHEDULE_CHANNEL_ID:
        missing.append("SCHEDULE_CHANNEL_ID")

    if missing:
        logger.error(
            "Отсутствуют обязательные переменные окружения: %s. "
            "Добавьте их в настройки хостинга.", ", ".join(missing)
        )
        return

    db = Database(DB_PATH)
    await db.init()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Middleware проверки прав админа
    dp.message.middleware(AdminMiddleware(db))
    dp.callback_query.middleware(AdminMiddleware(db))

    # Роутеры
    dp.include_router(user_router)
    dp.include_router(admin_router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
