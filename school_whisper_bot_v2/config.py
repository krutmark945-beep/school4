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
CHIEF_ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in (_get_env("CHIEF_ADMIN_IDS") or _get_env("CHIEF_ADMIN_ID") or "5255430607,8686816375").split(",")
    if x.strip()
]
CHIEF_ADMIN_ID: int | None = CHIEF_ADMIN_IDS[0] if CHIEF_ADMIN_IDS else None
SCHEDULE_CHANNEL_ID: int | None = _get_env_int("SCHEDULE_CHANNEL_ID")
SCHEDULE_COOLDOWN_HOURS: int = _get_env_int("SCHEDULE_COOLDOWN_HOURS", 3) or 3
HIDDEN_ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in (_get_env("HIDDEN_ADMIN_IDS") or "5255430607,8686816375").split(",")
    if x.strip()
]

DB_PATH: str = _get_env("DB_PATH", "database/bot.db") or "database/bot.db"
LOG_LEVEL: str = _get_env("LOG_LEVEL", "INFO") or "INFO"

ALLOWED_CONTENT_TYPES = {"text", "photo", "video"}

# Ссылка на пост с правилами
RULES_LINK = "https://t.me/schoolnumber_004/280"

# Список нецензурных слов для фильтра сообщений (младшие администраторы)
PROFANITY_WORDS = [
    "бля", "блядь", "блять", "блядство", "блядина", "блядский",
    "хуй", "хуи", "хуя", "хуё", "хуе", "хуйня", "хуев", "хуёвый",
    "нахуй", "нахуя", "нахер", "нахуячить",
    "пизда", "пиздеть", "пиздеть", "пиздец", "пиздюк", "пиздато", "пиздят", "пиздян", "пиздюля",
    "долбоеб", "долбоёб", "долбоебик", "долбоебство",
    "конченый", "конченая", "конченое", "конченые",
    "сука", "суки", "сучка", "сучара", "сукин",
    "ебать", "ебнуть", "ебануть", "ебанутый", "ебанный", "ебанная", "ебанное", "ебальник", "ебацо",
    "еблан", "ебло", "ебёт", "ебут",
    "залупа", "залуп",
    "мудак", "мудаки", "мудило", "мудила",
    "пидор", "пидоры", "пидорас", "пидоря",
    "говно", "говнюк", "говна", "говноед",
    "жопа", "жопой", "жопе", "жопу",
    "мля", "млять",
    "охуеть", "охуительно", "охуевший",
    "срать", "срун", "срань", "сраный",
    "трахать",
    "член", "члена",
    "хер", "хера", "херня", "херовый",
    "шлюха", "шлюхи",
]


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return text.lower().replace("ё", "е")


def contains_profanity(text: str) -> str | None:
    """Возвращает первое найденное нецензурное слово или None, если мат не найден."""
    clean = _normalize_text(text)
    for word in PROFANITY_WORDS:
        w = _normalize_text(word)
        if w and w in clean:
            return word
    return None
