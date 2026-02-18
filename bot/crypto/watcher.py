from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.admin.notifier import send_message_to_admins
from bot.config.settings import Settings
from bot.database.session import session_scope
from bot.models import User
from bot.services.deposit_service import DepositService

logger = logging.getLogger(__name__)


async def tron_watcher_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    application = context.application
    settings: Settings = application.bot_data["settings"]
    tron_client = application.bot_data.get("tron_client")

    if not settings.tron_wallet_address or tron_client is None:
        return

    try:
        txs = tron_client.fetch_incoming_trx(settings.tron_wallet_address)
    except Exception:
        logger.exception("Failed to fetch TRX transfers")
        return

    if not txs:
        return

    matches: list[dict[str, Any]] = []

    with session_scope() as session:
        open_requests = DepositService.list_open_crypto_requests_for_detection(session)
        if not open_requests:
            return

        known_hashes = DepositService.known_tx_hashes(session)
        for tx in sorted(txs, key=lambda item: item["timestamp_ms"]):
            tx_hash = tx["tx_hash"]
            if tx_hash in known_hashes:
                continue

            match = DepositService.find_matching_request_for_amount(
                open_requests,
                tx["amount_trx"],
                tx["timestamp_ms"],
            )
            if not match:
                continue

            detected = DepositService.mark_crypto_detected(
                session,
                match.id,
                tx_hash,
                tx.get("from_address"),
            )
            user = session.get(User, detected.user_id)
            if user:
                matches.append(
                    {
                        "request_id": detected.id,
                        "user_tg_id": user.telegram_id,
                        "expected_trx": str(detected.expected_trx),
                        "tx_hash": tx_hash,
                    }
                )
            known_hashes.add(tx_hash)
            open_requests = [r for r in open_requests if r.id != match.id]

    if not matches:
        return

    for item in matches:
        text = (
            "Yeni TRX odeme tespit edildi.\n"
            f"Crypto Request: #{item['request_id']}\n"
            f"Beklenen: {item['expected_trx']} TRX\n"
            f"TX: `{item['tx_hash']}`\n"
            "Onay icin admin panelden veya asagidaki butondan devam edin."
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Onayla", callback_data=f"admin_crypto_ok:{item['request_id']}")]]
        )
        await send_message_to_admins(application, settings, text=text, reply_markup=markup)

        try:
            await application.bot.send_message(
                chat_id=item["user_tg_id"],
                text=(
                    "TRX odemeniz tespit edildi.\n"
                    "Guvenlik nedeniyle coin yukleme otomatik degildir. Admin onayi bekleniyor."
                ),
            )
        except Exception:
            logger.exception("Failed to notify user for detected TRX", extra=item)
