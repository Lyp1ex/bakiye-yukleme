from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application

from bot.config.settings import Settings
from bot.database.session import session_scope
from bot.models import CryptoDepositRequest, DepositRequest, RequestStatusCard, WithdrawalRequest

logger = logging.getLogger(__name__)

FLOW_BANK = "bank"
FLOW_CRYPTO = "crypto"
FLOW_WITHDRAW = "withdraw"

FLOW_TITLE_MAP = {
    FLOW_BANK: "Banka Bakiye Yükleme",
    FLOW_CRYPTO: "TRX Bakiye Yükleme",
    FLOW_WITHDRAW: "Bakiye Çekim Talebi",
}

STATUS_TEXT_MAP = {
    "pending": "Beklemede",
    "approved": "Onaylandı",
    "rejected": "Reddedildi",
    "pending_payment": "Ödeme Bekleniyor",
    "detected": "Ödeme Tespit Edildi",
    "paid_waiting_proof": "SS Bekleniyor",
    "completed": "Tamamlandı",
}


@dataclass
class CardSnapshot:
    flow_type: str
    request_id: int
    request_code: str
    user_id: int
    user_telegram_id: int
    status: str
    status_text: str
    title: str
    amount_line: str
    next_step: str
    queue_line: str
    created_at: datetime | None
    updated_at: datetime | None
    is_closed: bool


@dataclass
class SlaEscalation:
    flow_type: str
    request_id: int
    request_code: str
    user_telegram_id: int
    age_minutes: int
    level: int
    status_text: str


def _status_text(status: str) -> str:
    return STATUS_TEXT_MAP.get(status, status)


def _request_code(request_id: int) -> str:
    return f"DS-#{request_id}"


def _format_ts(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")


def _flow_title(flow_type: str) -> str:
    return FLOW_TITLE_MAP.get(flow_type, flow_type)


def _next_step(flow_type: str, status: str) -> str:
    if flow_type == FLOW_BANK:
        if status == "pending":
            return "Dekont admin tarafından inceleniyor."
        if status == "approved":
            return "Bakiye hesabınıza eklendi."
        if status == "rejected":
            return "Dilerseniz itiraz kaydı oluşturabilirsiniz."
    if flow_type == FLOW_CRYPTO:
        if status == "pending_payment":
            return "Transferin cüzdana düşmesi bekleniyor."
        if status == "detected":
            return "Transfer tespit edildi, admin onayı bekleniyor."
        if status == "approved":
            return "Bakiye hesabınıza eklendi."
        if status == "rejected":
            return "Dilerseniz itiraz kaydı oluşturabilirsiniz."
    if flow_type == FLOW_WITHDRAW:
        if status == "pending":
            return "Çekim talebiniz ödeme sırasına alındı."
        if status == "paid_waiting_proof":
            return "Ödeme sonrası ekran görüntüsü (SS) bekleniyor."
        if status == "completed":
            return "Çekim işlemi tamamlandı."
        if status == "rejected":
            return "Tutar bakiyenize iade edildi."
    return "Talep durumunu takipte kalın."


def _is_closed(flow_type: str, status: str) -> bool:
    if flow_type == FLOW_BANK:
        return status in {"approved", "rejected"}
    if flow_type == FLOW_CRYPTO:
        return status in {"approved", "rejected"}
    if flow_type == FLOW_WITHDRAW:
        return status in {"completed", "rejected"}
    return False


def _append_timeline(card: RequestStatusCard, line: str) -> None:
    clean = line.strip()
    if not clean:
        return
    stamp = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
    entry = f"{stamp} • {clean}"
    items = [v for v in (card.timeline_text or "").split("\n") if v.strip()]
    if items and items[-1].endswith(clean):
        return
    items.append(entry)
    card.timeline_text = "\n".join(items[-8:])


def _card_markup(settings: Settings, flow_type: str, request_id: int) -> InlineKeyboardMarkup:
    support_url = f"https://t.me/{settings.support_username}"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yenile", callback_data=f"user_card_refresh:{flow_type}:{request_id}"),
                InlineKeyboardButton("İtiraz", callback_data=f"user_card_appeal:{flow_type}:{request_id}"),
            ],
            [InlineKeyboardButton("Desteğe Yaz", url=support_url)],
        ]
    )


def _render_card_text(snapshot: CardSnapshot, card: RequestStatusCard, settings: Settings) -> str:
    lines = [
        "📌 CANLI TALEP KARTI",
        f"Kod: {snapshot.request_code}",
        f"İşlem: {snapshot.title}",
        f"Durum: {snapshot.status_text}",
        f"{snapshot.amount_line}",
        f"Sıradaki Adım: {snapshot.next_step}",
    ]
    if snapshot.queue_line:
        lines.append(snapshot.queue_line)
    lines.append(f"Son Güncelleme: {_format_ts(snapshot.updated_at)}")
    lines.append("")
    lines.append("Zaman Çizelgesi:")
    timeline_items = [v for v in (card.timeline_text or "").split("\n") if v.strip()]
    if timeline_items:
        lines.extend([f"- {item}" for item in timeline_items[-8:]])
    else:
        lines.append("- Kayıt bulunamadı.")
    lines.append("")
    lines.append(f"Destek: @{settings.support_username}")
    return "\n".join(lines)


class StatusCardService:
    @staticmethod
    def get_card(session: Session, flow_type: str, request_id: int) -> RequestStatusCard | None:
        return session.scalar(
            select(RequestStatusCard).where(
                RequestStatusCard.flow_type == flow_type,
                RequestStatusCard.request_id == request_id,
            )
        )

    @staticmethod
    def list_overdue_cards(
        session: Session,
        settings: Settings,
        *,
        min_age_minutes: int,
        limit: int = 40,
    ) -> list[SlaEscalation]:
        cards = list(
            session.scalars(
                select(RequestStatusCard)
                .where(RequestStatusCard.is_closed.is_(False))
                .order_by(desc(RequestStatusCard.created_at))
                .limit(max(limit, 1))
            ).all()
        )
        items: list[SlaEscalation] = []
        for card in cards:
            snap = StatusCardService._snapshot(session, settings, card.flow_type, card.request_id)
            if not snap or snap.is_closed:
                continue
            age_minutes = StatusCardService._age_minutes(snap.created_at)
            if age_minutes < min_age_minutes:
                continue
            items.append(
                SlaEscalation(
                    flow_type=card.flow_type,
                    request_id=card.request_id,
                    request_code=card.request_code,
                    user_telegram_id=card.user_telegram_id,
                    age_minutes=age_minutes,
                    level=StatusCardService._sla_level(settings, age_minutes),
                    status_text=snap.status_text,
                )
            )
        items.sort(key=lambda x: x.age_minutes, reverse=True)
        return items[:limit]

    @staticmethod
    def prepare_sla_escalations(session: Session, settings: Settings) -> list[SlaEscalation]:
        cards = list(
            session.scalars(
                select(RequestStatusCard)
                .where(RequestStatusCard.is_closed.is_(False))
                .order_by(desc(RequestStatusCard.updated_at))
                .limit(500)
            ).all()
        )
        escalations: list[SlaEscalation] = []

        for card in cards:
            snap = StatusCardService._snapshot(session, settings, card.flow_type, card.request_id)
            if not snap:
                card.is_closed = True
                continue

            card.current_status = snap.status
            card.is_closed = snap.is_closed
            if card.is_closed:
                continue

            age_minutes = StatusCardService._age_minutes(snap.created_at)
            level = StatusCardService._sla_level(settings, age_minutes)
            if level <= 0 or level <= int(card.last_sla_level or 0):
                continue

            card.last_sla_level = level
            _append_timeline(
                card,
                f"SLA-{level}: Talep bekleme süresi {age_minutes} dakikayı aştı.",
            )
            escalations.append(
                SlaEscalation(
                    flow_type=card.flow_type,
                    request_id=card.request_id,
                    request_code=card.request_code,
                    user_telegram_id=card.user_telegram_id,
                    age_minutes=age_minutes,
                    level=level,
                    status_text=snap.status_text,
                )
            )
        return escalations

    @staticmethod
    async def sync_card(
        application: Application,
        settings: Settings,
        flow_type: str,
        request_id: int,
        *,
        event_text: str | None = None,
        user_notice: str | None = None,
        sla_level: int | None = None,
    ) -> bool:
        with session_scope() as session:
            snap = StatusCardService._snapshot(session, settings, flow_type, request_id)
            if not snap:
                return False

            card = StatusCardService._get_or_create_card(session, snap)
            if event_text:
                _append_timeline(card, event_text)

            card.current_status = snap.status
            card.is_closed = snap.is_closed
            if sla_level is not None:
                card.last_sla_level = max(int(card.last_sla_level or 0), int(sla_level))

            text = _render_card_text(snap, card, settings)
            reply_markup = _card_markup(settings, flow_type, request_id)
            chat_id = int(card.chat_id or snap.user_telegram_id)
            message_id = int(card.message_id or 0) or None

        final_chat_id = chat_id
        final_message_id = message_id

        edited = False
        if message_id:
            try:
                await application.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
                edited = True
            except BadRequest:
                edited = False
            except Exception:
                logger.exception(
                    "Canlı talep kartı düzenlenemedi",
                    extra={"flow_type": flow_type, "request_id": request_id},
                )

        if not edited:
            try:
                sent = await application.bot.send_message(
                    chat_id=snap.user_telegram_id,
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
                final_chat_id = sent.chat_id
                final_message_id = sent.message_id
            except Exception:
                logger.exception(
                    "Canlı talep kartı gönderilemedi",
                    extra={"flow_type": flow_type, "request_id": request_id},
                )
                return False

        if user_notice:
            try:
                await application.bot.send_message(chat_id=snap.user_telegram_id, text=user_notice)
            except Exception:
                logger.exception(
                    "Canlı talep kartı bilgilendirme mesajı gönderilemedi",
                    extra={"flow_type": flow_type, "request_id": request_id},
                )

        with session_scope() as session:
            card = StatusCardService.get_card(session, flow_type, request_id)
            if card:
                card.chat_id = int(final_chat_id)
                card.message_id = int(final_message_id)

        return True

    @staticmethod
    def is_rejected_for_appeal(session: Session, flow_type: str, request_id: int, user_id: int) -> bool:
        if flow_type == FLOW_BANK:
            row = session.get(DepositRequest, request_id)
            return bool(row and row.user_id == user_id and row.status == "rejected")
        if flow_type == FLOW_CRYPTO:
            row = session.get(CryptoDepositRequest, request_id)
            return bool(row and row.user_id == user_id and row.status == "rejected")
        if flow_type == FLOW_WITHDRAW:
            row = session.get(WithdrawalRequest, request_id)
            return bool(row and row.user_id == user_id and row.status == "rejected")
        return False

    @staticmethod
    def is_request_owned_by_user(session: Session, flow_type: str, request_id: int, user_id: int) -> bool:
        if flow_type == FLOW_BANK:
            row = session.get(DepositRequest, request_id)
            return bool(row and row.user_id == user_id)
        if flow_type == FLOW_CRYPTO:
            row = session.get(CryptoDepositRequest, request_id)
            return bool(row and row.user_id == user_id)
        if flow_type == FLOW_WITHDRAW:
            row = session.get(WithdrawalRequest, request_id)
            return bool(row and row.user_id == user_id)
        return False

    @staticmethod
    def _age_minutes(created_at: datetime | None) -> int:
        if not created_at:
            return 0
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)
        return max(0, int(diff.total_seconds() // 60))

    @staticmethod
    def _sla_level(settings: Settings, age_minutes: int) -> int:
        if age_minutes >= settings.sla_level3_minutes:
            return 3
        if age_minutes >= settings.sla_level2_minutes:
            return 2
        if age_minutes >= settings.sla_level1_minutes:
            return 1
        return 0

    @staticmethod
    def _get_or_create_card(session: Session, snapshot: CardSnapshot) -> RequestStatusCard:
        card = StatusCardService.get_card(session, snapshot.flow_type, snapshot.request_id)
        if card:
            if not card.timeline_text:
                _append_timeline(card, "Canlı talep kartı senkronize edildi.")
            return card

        card = RequestStatusCard(
            user_id=snapshot.user_id,
            user_telegram_id=snapshot.user_telegram_id,
            flow_type=snapshot.flow_type,
            request_id=snapshot.request_id,
            request_code=snapshot.request_code,
            current_status=snapshot.status,
            is_closed=snapshot.is_closed,
        )
        session.add(card)
        session.flush()
        _append_timeline(card, "Talep oluşturuldu ve sıraya alındı.")
        return card

    @staticmethod
    def _snapshot(
        session: Session,
        settings: Settings,
        flow_type: str,
        request_id: int,
    ) -> CardSnapshot | None:
        if flow_type == FLOW_BANK:
            row = session.scalar(
                select(DepositRequest)
                .options(joinedload(DepositRequest.user), joinedload(DepositRequest.package))
                .where(DepositRequest.id == request_id)
            )
            if not row or not row.user or not row.package:
                return None
            queue_line = ""
            if row.status == "pending":
                total = int(session.scalar(select(func.count(DepositRequest.id)).where(DepositRequest.status == "pending")) or 0)
                position = int(
                    session.scalar(
                        select(func.count(DepositRequest.id)).where(
                            DepositRequest.status == "pending",
                            DepositRequest.id <= row.id,
                        )
                    )
                    or 0
                )
                eta = position * max(settings.bank_queue_eta_min_per_request, 1)
                queue_line = f"Sıra: {position}/{total} | Tahmini Süre: {eta} dk"
            return CardSnapshot(
                flow_type=FLOW_BANK,
                request_id=row.id,
                request_code=_request_code(row.id),
                user_id=row.user_id,
                user_telegram_id=row.user.telegram_id,
                status=row.status,
                status_text=_status_text(row.status),
                title=_flow_title(FLOW_BANK),
                amount_line=f"Tutar: {int(row.package.coin_amount)} BAKİYE | {row.package.try_price} TL",
                next_step=_next_step(FLOW_BANK, row.status),
                queue_line=queue_line,
                created_at=row.created_at,
                updated_at=row.updated_at,
                is_closed=_is_closed(FLOW_BANK, row.status),
            )

        if flow_type == FLOW_CRYPTO:
            row = session.scalar(
                select(CryptoDepositRequest)
                .options(joinedload(CryptoDepositRequest.user), joinedload(CryptoDepositRequest.package))
                .where(CryptoDepositRequest.id == request_id)
            )
            if not row or not row.user:
                return None
            queue_line = ""
            if row.status in {"pending_payment", "detected"}:
                total = int(
                    session.scalar(
                        select(func.count(CryptoDepositRequest.id)).where(
                            CryptoDepositRequest.status.in_(["pending_payment", "detected"])
                        )
                    )
                    or 0
                )
                position = int(
                    session.scalar(
                        select(func.count(CryptoDepositRequest.id)).where(
                            CryptoDepositRequest.status.in_(["pending_payment", "detected"]),
                            CryptoDepositRequest.id <= row.id,
                        )
                    )
                    or 0
                )
                eta = position * max(settings.crypto_queue_eta_min_per_request, 1)
                queue_line = f"Sıra: {position}/{total} | Tahmini Süre: {eta} dk"
            return CardSnapshot(
                flow_type=FLOW_CRYPTO,
                request_id=row.id,
                request_code=_request_code(row.id),
                user_id=row.user_id,
                user_telegram_id=row.user.telegram_id,
                status=row.status,
                status_text=_status_text(row.status),
                title=_flow_title(FLOW_CRYPTO),
                amount_line=f"Tutar: {row.expected_trx} TRX",
                next_step=_next_step(FLOW_CRYPTO, row.status),
                queue_line=queue_line,
                created_at=row.created_at,
                updated_at=row.updated_at,
                is_closed=_is_closed(FLOW_CRYPTO, row.status),
            )

        if flow_type == FLOW_WITHDRAW:
            row = session.scalar(
                select(WithdrawalRequest)
                .options(joinedload(WithdrawalRequest.user))
                .where(WithdrawalRequest.id == request_id)
            )
            if not row or not row.user:
                return None
            queue_line = ""
            if row.status == "pending":
                total = int(
                    session.scalar(select(func.count(WithdrawalRequest.id)).where(WithdrawalRequest.status == "pending")) or 0
                )
                position = int(
                    session.scalar(
                        select(func.count(WithdrawalRequest.id)).where(
                            WithdrawalRequest.status == "pending",
                            WithdrawalRequest.id <= row.id,
                        )
                    )
                    or 0
                )
                eta = position * max(settings.withdraw_queue_eta_min_per_request, 1)
                queue_line = f"Sıra: {position}/{total} | Tahmini Süre: {eta} dk"
            return CardSnapshot(
                flow_type=FLOW_WITHDRAW,
                request_id=row.id,
                request_code=_request_code(row.id),
                user_id=row.user_id,
                user_telegram_id=row.user.telegram_id,
                status=row.status,
                status_text=_status_text(row.status),
                title=_flow_title(FLOW_WITHDRAW),
                amount_line=f"Tutar: {int(row.amount_coins)} BAKİYE",
                next_step=_next_step(FLOW_WITHDRAW, row.status),
                queue_line=queue_line,
                created_at=row.created_at,
                updated_at=row.updated_at,
                is_closed=_is_closed(FLOW_WITHDRAW, row.status),
            )
        return None
