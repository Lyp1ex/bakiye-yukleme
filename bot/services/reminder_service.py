from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import asc, select
from sqlalchemy.orm import Session, joinedload

from bot.models import CryptoDepositRequest, DepositRequest, ReminderEvent, WithdrawalRequest
from bot.utils.constants import (
    CRYPTO_STATUS_DETECTED,
    CRYPTO_STATUS_PENDING_PAYMENT,
    DEPOSIT_STATUS_PENDING,
    WITHDRAWAL_STATUS_PENDING,
)

ENTITY_BANK = "bank_deposit"
ENTITY_CRYPTO = "crypto_deposit"
ENTITY_WITHDRAW = "withdrawal"


@dataclass
class ReminderTarget:
    entity_type: str
    entity_id: int
    user_telegram_id: int
    created_at: datetime | None
    status: str


class ReminderService:
    @staticmethod
    def _threshold(minutes: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(minutes=max(minutes, 1))

    @staticmethod
    def can_send(
        session: Session,
        entity_type: str,
        entity_id: int,
        cooldown_minutes: int,
    ) -> bool:
        row = session.scalar(
            select(ReminderEvent).where(
                ReminderEvent.entity_type == entity_type,
                ReminderEvent.entity_id == entity_id,
            )
        )
        if not row:
            return True
        diff = datetime.now(timezone.utc) - (row.last_sent_at or datetime.now(timezone.utc))
        return diff.total_seconds() >= max(cooldown_minutes, 1) * 60

    @staticmethod
    def mark_sent(session: Session, entity_type: str, entity_id: int) -> ReminderEvent:
        row = session.scalar(
            select(ReminderEvent).where(
                ReminderEvent.entity_type == entity_type,
                ReminderEvent.entity_id == entity_id,
            )
        )
        now = datetime.now(timezone.utc)
        if row:
            row.send_count += 1
            row.last_sent_at = now
            session.flush()
            return row

        row = ReminderEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            send_count=1,
            last_sent_at=now,
        )
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def list_due_bank(session: Session, min_age_minutes: int) -> list[ReminderTarget]:
        threshold = ReminderService._threshold(min_age_minutes)
        rows = session.scalars(
            select(DepositRequest)
            .options(joinedload(DepositRequest.user))
            .where(
                DepositRequest.status == DEPOSIT_STATUS_PENDING,
                DepositRequest.created_at <= threshold,
            )
            .order_by(asc(DepositRequest.id))
        ).all()
        result: list[ReminderTarget] = []
        for row in rows:
            if not row.user:
                continue
            result.append(
                ReminderTarget(
                    entity_type=ENTITY_BANK,
                    entity_id=row.id,
                    user_telegram_id=row.user.telegram_id,
                    created_at=row.created_at,
                    status=row.status,
                )
            )
        return result

    @staticmethod
    def list_due_crypto(session: Session, min_age_minutes: int) -> list[ReminderTarget]:
        threshold = ReminderService._threshold(min_age_minutes)
        rows = session.scalars(
            select(CryptoDepositRequest)
            .options(joinedload(CryptoDepositRequest.user))
            .where(
                CryptoDepositRequest.status.in_([CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED]),
                CryptoDepositRequest.created_at <= threshold,
            )
            .order_by(asc(CryptoDepositRequest.id))
        ).all()
        result: list[ReminderTarget] = []
        for row in rows:
            if not row.user:
                continue
            result.append(
                ReminderTarget(
                    entity_type=ENTITY_CRYPTO,
                    entity_id=row.id,
                    user_telegram_id=row.user.telegram_id,
                    created_at=row.created_at,
                    status=row.status,
                )
            )
        return result

    @staticmethod
    def list_due_withdraw(session: Session, min_age_minutes: int) -> list[ReminderTarget]:
        threshold = ReminderService._threshold(min_age_minutes)
        rows = session.scalars(
            select(WithdrawalRequest)
            .options(joinedload(WithdrawalRequest.user))
            .where(
                WithdrawalRequest.status == WITHDRAWAL_STATUS_PENDING,
                WithdrawalRequest.created_at <= threshold,
            )
            .order_by(asc(WithdrawalRequest.id))
        ).all()
        result: list[ReminderTarget] = []
        for row in rows:
            if not row.user:
                continue
            result.append(
                ReminderTarget(
                    entity_type=ENTITY_WITHDRAW,
                    entity_id=row.id,
                    user_telegram_id=row.user.telegram_id,
                    created_at=row.created_at,
                    status=row.status,
                )
            )
        return result

