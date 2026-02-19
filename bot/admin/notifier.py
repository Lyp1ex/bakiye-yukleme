from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup
from telegram.ext import Application

from bot.config.settings import Settings

logger = logging.getLogger(__name__)


async def send_message_to_admins(
    application: Application,
    settings: Settings,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    for admin_id in settings.admin_ids:
        try:
            await application.bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Admin mesajı gönderilemedi", extra={"admin_id": admin_id})


async def send_receipt_to_admins(
    application: Application,
    settings: Settings,
    receipt_file_id: str,
    file_type: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    for admin_id in settings.admin_ids:
        try:
            if file_type == "document":
                await application.bot.send_document(
                    chat_id=admin_id,
                    document=receipt_file_id,
                    caption=caption,
                    reply_markup=reply_markup,
                )
            else:
                await application.bot.send_photo(
                    chat_id=admin_id,
                    photo=receipt_file_id,
                    caption=caption,
                    reply_markup=reply_markup,
                )
        except Exception:
            logger.exception("Admin dekont bildirimi gönderilemedi", extra={"admin_id": admin_id})
