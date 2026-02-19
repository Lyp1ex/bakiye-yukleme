from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session, joinedload

from bot.models import User, WithdrawalRequest
from bot.services.admin_service import AdminService
from bot.utils.constants import (
    LOG_ENTITY_WITHDRAWAL,
    WITHDRAWAL_STATUS_COMPLETED,
    WITHDRAWAL_STATUS_PAID_WAITING_PROOF,
    WITHDRAWAL_STATUS_PENDING,
    WITHDRAWAL_STATUS_REJECTED,
)


class WithdrawalService:
    @staticmethod
    def list_pending_requests(session: Session) -> list[WithdrawalRequest]:
        stmt = (
            select(WithdrawalRequest)
            .options(joinedload(WithdrawalRequest.user))
            .where(WithdrawalRequest.status == WITHDRAWAL_STATUS_PENDING)
            .order_by(asc(WithdrawalRequest.id))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_user_requests(
        session: Session,
        user_id: int,
        limit: int = 20,
    ) -> list[WithdrawalRequest]:
        stmt = (
            select(WithdrawalRequest)
            .where(WithdrawalRequest.user_id == user_id)
            .order_by(desc(WithdrawalRequest.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def has_pending_request(session: Session, user_id: int) -> bool:
        stmt = (
            select(WithdrawalRequest.id)
            .where(
                WithdrawalRequest.user_id == user_id,
                WithdrawalRequest.status == WITHDRAWAL_STATUS_PENDING,
            )
            .limit(1)
        )
        return session.scalar(stmt) is not None

    @staticmethod
    def create_full_balance_request(
        session: Session,
        user_id: int,
        full_name: str,
        iban: str,
        bank_name: str,
    ) -> WithdrawalRequest:
        user = session.get(User, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı")
        if user.coin_balance <= 0:
            raise ValueError("Çekim için bakiyeniz bulunmuyor")
        if WithdrawalService.has_pending_request(session, user_id):
            raise ValueError("Zaten bekleyen bir çekim talebiniz var")

        amount = int(user.coin_balance)
        user.coin_balance = 0

        req = WithdrawalRequest(
            user_id=user_id,
            amount_coins=amount,
            full_name=full_name.strip(),
            iban=iban.strip().replace(" ", "").upper(),
            bank_name=bank_name.strip(),
            status=WITHDRAWAL_STATUS_PENDING,
        )
        session.add(req)
        session.flush()
        return req

    @staticmethod
    def approve_request(
        session: Session,
        request_id: int,
        admin_id: int,
        note: str = "",
    ) -> WithdrawalRequest:
        req = session.get(WithdrawalRequest, request_id)
        if not req:
            raise ValueError("Çekim talebi bulunamadı")
        if req.status != WITHDRAWAL_STATUS_PENDING:
            raise ValueError("Çekim talebi onaya uygun değil")

        req.status = WITHDRAWAL_STATUS_PAID_WAITING_PROOF
        req.approved_by = admin_id
        req.admin_note = note or None

        AdminService.log_action(
            session,
            admin_id,
            "approve_withdrawal",
            LOG_ENTITY_WITHDRAWAL,
            req.id,
            f"amount={req.amount_coins}; user_id={req.user_id}",
        )
        session.flush()
        return req

    @staticmethod
    def reject_request(
        session: Session,
        request_id: int,
        admin_id: int,
        note: str = "",
    ) -> WithdrawalRequest:
        req = session.get(WithdrawalRequest, request_id)
        if not req:
            raise ValueError("Çekim talebi bulunamadı")
        if req.status != WITHDRAWAL_STATUS_PENDING:
            raise ValueError("Çekim talebi reddetmeye uygun değil")

        user = session.get(User, req.user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı")

        user.coin_balance += int(req.amount_coins)
        req.status = WITHDRAWAL_STATUS_REJECTED
        req.approved_by = admin_id
        req.admin_note = note or None

        AdminService.log_action(
            session,
            admin_id,
            "reject_withdrawal",
            LOG_ENTITY_WITHDRAWAL,
            req.id,
            f"amount={req.amount_coins}; note={note or '-'}",
        )
        session.flush()
        return req

    @staticmethod
    def get_latest_waiting_proof_for_user(session: Session, user_id: int) -> WithdrawalRequest | None:
        stmt = (
            select(WithdrawalRequest)
            .where(
                WithdrawalRequest.user_id == user_id,
                WithdrawalRequest.status == WITHDRAWAL_STATUS_PAID_WAITING_PROOF,
            )
            .order_by(desc(WithdrawalRequest.id))
            .limit(1)
        )
        return session.scalar(stmt)

    @staticmethod
    def submit_proof(
        session: Session,
        request_id: int,
        proof_file_id: str,
        proof_file_type: str,
    ) -> WithdrawalRequest:
        req = session.get(WithdrawalRequest, request_id)
        if not req:
            raise ValueError("Çekim talebi bulunamadı")
        if req.status != WITHDRAWAL_STATUS_PAID_WAITING_PROOF:
            raise ValueError("Bu talep için SS yükleme beklenmiyor")

        req.proof_file_id = proof_file_id
        req.proof_file_type = proof_file_type
        req.proof_received_at = datetime.now(timezone.utc)
        req.status = WITHDRAWAL_STATUS_COMPLETED
        session.flush()
        return req
