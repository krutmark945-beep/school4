import logging
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from config import CHIEF_ADMIN_IDS
from database.db import Database

logger = logging.getLogger(__name__)


class AdminMiddleware(BaseMiddleware):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    async def on_pre_process_message(self, message: Message, data: dict):
        data["db"] = self.db
        user = message.from_user
        if not user:
            data["is_chief"] = False
            data["is_admin"] = False
            data["user_role"] = None
            return
        data["is_chief"] = user.id in CHIEF_ADMIN_IDS
        data["is_admin"] = data["is_chief"] or await self.db.is_admin(user.id)
        data["user_role"] = "chief" if data["is_chief"] else await self.db.get_admin_role(user.id)

    async def on_pre_process_callback_query(self, call: CallbackQuery, data: dict):
        data["db"] = self.db
        user = call.from_user
        if not user:
            data["is_chief"] = False
            data["is_admin"] = False
            data["user_role"] = None
            return
        data["is_chief"] = user.id in CHIEF_ADMIN_IDS
        data["is_admin"] = data["is_chief"] or await self.db.is_admin(user.id)
        data["user_role"] = "chief" if data["is_chief"] else await self.db.get_admin_role(user.id)
