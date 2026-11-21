import os
from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Переменная окружения {name} не задана")
    return value


BOT_TOKEN: str = _get_env("BOT_TOKEN")
CHIEF_ADMIN_ID: int = int(_get_env("CHIEF_ADMIN_ID"))
SCHEDULE_CHANNEL_ID: int = int(_get_env("SCHEDULE_CHANNEL_ID"))
SCHEDULE_COOLDOWN_HOURS: int = int(_get_env("SCHEDULE_COOLDOWN_HOURS", "3"))

DB_PATH: str = _get_env("DB_PATH", "database/bot.db")
LOG_LEVEL: str = _get_env("LOG_LEVEL", "INFO")

# Разрешаем только эти типы контента от пользователей
ALLOWED_CONTENT_TYPES = {"text", "photo", "video"}
