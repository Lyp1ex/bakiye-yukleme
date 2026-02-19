from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.admin.notifier import send_message_to_admins
from bot.config.settings import Settings
from bot.database.session import session_scope
from bot.models import User
from bot.services import AuditService, StatusCardService
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
        logger.exception("TRX transferleri alınamadı")
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
            AuditService.log_system_action(
                session,
                action="crypto_tx_detected",
                entity_type="crypto_deposit",
                entity_id=detected.id,
                details=f"tx_hash={tx_hash}; amount_trx={tx['amount_trx']}",
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
            "Yeni TRX ödeme tespit edildi.\n"
            f"Kripto Talebi: #{item['request_id']}\n"
            f"Beklenen: {item['expected_trx']} TRX\n"
            f"TX: `{item['tx_hash']}`\n"
            "Onay için admin panelden veya aşağıdaki butondan devam edin."
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Onayla", callback_data=f"admin_crypto_ok:{item['request_id']}")]]
        )
        await send_message_to_admins(application, settings, text=text, reply_markup=markup)

        try:
            await application.bot.send_message(
                chat_id=item["user_tg_id"],
                text=(
                    "TRX ödemeniz tespit edildi.\n"
                    "Güvenlik nedeniyle bakiye yükleme otomatik değildir. Admin onayı bekleniyor."
                ),
            )
        except Exception:
            logger.exception("Tespit edilen TRX için kullanıcı bildirimi gönderilemedi", extra=item)

        try:
            await StatusCardService.sync_card(
                application,
                settings,
                "crypto",
                item["request_id"],
                event_text="TRX transferi tespit edildi, admin onayı bekleniyor.",
            )
        except Exception:
            logger.exception("Kripto canlı talep kartı güncellenemedi", extra=item)
