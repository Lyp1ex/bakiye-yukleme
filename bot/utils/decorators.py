from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from bot.config.settings import get_settings

settings = get_settings()

HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]



def admin_required(func: HandlerFunc) -> HandlerFunc:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or user.id not in settings.admin_ids:
            target = update.effective_message
            if target:
                await target.reply_text("Bu alan sadece adminler icin.")
            return
        return await func(update, context)

    return wrapper  # type: ignore[return-value]
