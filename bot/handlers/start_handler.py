from __future__ import annotations

from telegram.ext import CommandHandler

from bot.handlers.user_handler import start



def get_start_handler() -> CommandHandler:
    return CommandHandler("start", start)
