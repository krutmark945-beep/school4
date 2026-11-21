import asyncio
import logging
from aiogram import executor

from loader import dp, bot, logger
from config import BOT_TOKEN, CHIEF_ADMIN_ID, SCHEDULE_CHANNEL_ID, DB_PATH, LOG_LEVEL
from database.db import Database
from middlewares.admin_middleware import AdminMiddleware

# Регистрируем middleware
db = Database(DB_PATH)
dp.middleware.setup(AdminMiddleware(db))


async def on_startup(dp):
    """Выполняется при запуске бота."""
    await db.init()
    logger.info("Бот запущен и готов к работе")


async def on_shutdown(dp):
    """Выполняется при остановке бота."""
    logger.info("Бот остановлен")
    await bot.session.close()


def main():
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

    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
    )


if __name__ == "__main__":
    main()
