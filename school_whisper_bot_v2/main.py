import asyncio
import logging
from aiogram import executor

from loader import dp, bot, logger
from config import BOT_TOKEN, CHIEF_ADMIN_IDS, SCHEDULE_CHANNEL_ID, DB_PATH, LOG_LEVEL
from database.db import Database

# Регистрируем хендлеры (админские первыми, чтобы перехватывали кнопки раньше анонимных сообщений)
from handlers import admin_handlers, user_handlers  # noqa: F401

db = Database(DB_PATH)


async def on_startup(dp):
    """Выполняется при запуске бота."""
    await db.init()
    bot.db = db  # type: ignore[attr-defined]
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
    if not CHIEF_ADMIN_IDS:
        missing.append("CHIEF_ADMIN_IDS")
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
