import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from config import CHIEF_ADMIN_ID
from database.db import Database

logger = logging.getLogger(__name__)


class AdminMiddleware(BaseMiddleware):
    def __init__(self, db: Database):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)

        data["db"] = self.db
        is_chief = user.id == CHIEF_ADMIN_ID
        data["is_chief"] = is_chief
        data["is_admin"] = is_chief or await self.db.is_admin(user.id)
        data["user_role"] = "chief" if is_chief else await self.db.get_admin_role(user.id)

        return await handler(event, data)
