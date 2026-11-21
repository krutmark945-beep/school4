import aiosqlite
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from config import DB_PATH, CHIEF_ADMIN_ID

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _ensure_dir(self) -> None:
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    @asynccontextmanager
    async def _connect(self):
        self._ensure_dir()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def init(self) -> None:
        async with self._connect() as conn:
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER UNIQUE NOT NULL,
                    username      TEXT,
                    role          TEXT NOT NULL DEFAULT 'junior',
                    added_by      INTEGER,
                    added_at      TEXT NOT NULL,
                    is_active     INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS blocked_users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER UNIQUE NOT NULL,
                    blocked_by  INTEGER,
                    blocked_at  TEXT NOT NULL,
                    reason      TEXT
                );

                CREATE TABLE IF NOT EXISTS anonymous_messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    message_type    TEXT NOT NULL DEFAULT 'text',
                    file_id         TEXT,
                    text            TEXT,
                    created_at      TEXT NOT NULL,
                    is_blocked      INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS schedule_posts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id         TEXT NOT NULL,
                    caption         TEXT,
                    posted_by       INTEGER NOT NULL,
                    posted_at       TEXT NOT NULL,
                    next_allowed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_admins_user_id ON admins(user_id);
                CREATE INDEX IF NOT EXISTS idx_blocked_user_id ON blocked_users(user_id);
                CREATE INDEX IF NOT EXISTS idx_messages_user_id ON anonymous_messages(user_id);
                """
            )

            now = datetime.utcnow().isoformat()

            await conn.execute(
                "INSERT OR IGNORE INTO admins (user_id, username, role, added_by, added_at, is_active) "
                "VALUES (?, NULL, 'chief', NULL, ?, 1)",
                (CHIEF_ADMIN_ID, now),
            )

            defaults = {
                "schedule_channel_id": str(CHIEF_ADMIN_ID) if CHIEF_ADMIN_ID else "0",
                "schedule_cooldown_hours": "3",
            }
            for key, value in defaults.items():
                await conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )

            await conn.commit()
        logger.info("База данных инициализирована: %s", self.db_path)

    # ---------------- admins ----------------

    async def add_admin(
        self, user_id: int, username: str | None, added_by: int, role: str = "junior"
    ) -> bool:
        now = datetime.utcnow().isoformat()
        try:
            async with self._connect() as conn:
                await conn.execute(
                    "INSERT OR IGNORE INTO admins (user_id, username, role, added_by, added_at, is_active) "
                    "VALUES (?, ?, ?, ?, ?, 1)",
                    (user_id, username, role, added_by, now),
                )
                await conn.commit()
                return True
        except Exception:
            logger.exception("Ошибка добавления админа")
            return False

    async def remove_admin(self, user_id: int) -> bool:
        async with self._connect() as conn:
            cursor = await conn.execute(
                "UPDATE admins SET is_active = 0 WHERE user_id = ? AND role != 'chief'",
                (user_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_admins(self, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._connect() as conn:
            if active_only:
                async with conn.execute(
                    "SELECT * FROM admins WHERE is_active = 1 ORDER BY role DESC, added_at"
                ) as cur:
                    return [dict(r) for r in await cur.fetchall()]
            async with conn.execute("SELECT * FROM admins ORDER BY role DESC, added_at") as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def is_admin(self, user_id: int) -> bool:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT 1 FROM admins WHERE user_id = ? AND is_active = 1", (user_id,)
            ) as cur:
                return await cur.fetchone() is not None

    async def is_chief(self, user_id: int) -> bool:
        return user_id == CHIEF_ADMIN_ID

    async def get_admin_role(self, user_id: int) -> str | None:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT role FROM admins WHERE user_id = ? AND is_active = 1", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                return row["role"] if row else None

    # ---------------- blocked users ----------------

    async def block_user(
        self, user_id: int, blocked_by: int, reason: str | None = None
    ) -> bool:
        now = datetime.utcnow().isoformat()
        try:
            async with self._connect() as conn:
                await conn.execute(
                    "INSERT OR IGNORE INTO blocked_users (user_id, blocked_by, blocked_at, reason) "
                    "VALUES (?, ?, ?, ?)",
                    (user_id, blocked_by, now, reason),
                )
                await conn.commit()
                return True
        except Exception:
            logger.exception("Ошибка блокировки пользователя")
            return False

    async def is_blocked(self, user_id: int) -> bool:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT 1 FROM blocked_users WHERE user_id = ?", (user_id,)
            ) as cur:
                return await cur.fetchone() is not None

    async def get_blocked_users(self) -> list[dict[str, Any]]:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT * FROM blocked_users ORDER BY blocked_at DESC"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ---------------- anonymous messages ----------------

    async def add_anonymous_message(
        self, user_id: int, message_type: str, file_id: str | None, text: str | None
    ) -> int:
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            cursor = await conn.execute(
                "INSERT INTO anonymous_messages "
                "(user_id, message_type, file_id, text, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, message_type, file_id, text, now),
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_unblocked_messages(self) -> list[dict[str, Any]]:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT * FROM anonymous_messages WHERE is_blocked = 0 ORDER BY created_at DESC"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def mark_message_blocked(self, message_id: int) -> None:
        async with self._connect() as conn:
            await conn.execute(
                "UPDATE anonymous_messages SET is_blocked = 1 WHERE id = ?",
                (message_id,),
            )
            await conn.commit()

    # ---------------- schedule ----------------

    async def get_setting(self, key: str) -> str | None:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ) as cur:
                row = await cur.fetchone()
                return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        async with self._connect() as conn:
            await conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await conn.commit()

    async def get_last_schedule_post(self) -> dict[str, Any] | None:
        async with self._connect() as conn:
            async with conn.execute(
                "SELECT * FROM schedule_posts ORDER BY posted_at DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def add_schedule_post(
        self, file_id: str, caption: str | None, posted_by: int, next_allowed_at: str
    ) -> int:
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            cursor = await conn.execute(
                "INSERT INTO schedule_posts (file_id, caption, posted_by, posted_at, next_allowed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (file_id, caption, posted_by, now, next_allowed_at),
            )
            await conn.commit()
            return cursor.lastrowid
