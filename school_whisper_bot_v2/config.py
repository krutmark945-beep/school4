import os
from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def _get_env_int(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


BOT_TOKEN: str | None = _get_env("BOT_TOKEN")
CHIEF_ADMIN_ID: int | None = _get_env_int("CHIEF_ADMIN_ID")
SCHEDULE_CHANNEL_ID: int | None = _get_env_int("SCHEDULE_CHANNEL_ID")
SCHEDULE_COOLDOWN_HOURS: int = _get_env_int("SCHEDULE_COOLDOWN_HOURS", 3) or 3

DB_PATH: str = _get_env("DB_PATH", "database/bot.db") or "database/bot.db"
LOG_LEVEL: str = _get_env("LOG_LEVEL", "INFO") or "INFO"

ALLOWED_CONTENT_TYPES = {"text", "photo", "video"}
