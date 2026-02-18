from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session, joinedload

from bot.models import CoinPackage, CryptoDepositRequest, DepositRequest, User
from bot.services.admin_service import AdminService
from bot.utils.constants import (
    CRYPTO_STATUS_APPROVED,
    CRYPTO_STATUS_DETECTED,
    CRYPTO_STATUS_PENDING_PAYMENT,
    CRYPTO_STATUS_REJECTED,
    DEPOSIT_STATUS_APPROVED,
    DEPOSIT_STATUS_PENDING,
    DEPOSIT_STATUS_REJECTED,
    LOG_ENTITY_BANK_DEPOSIT,
    LOG_ENTITY_CRYPTO_DEPOSIT,
)


class DepositService:
    @staticmethod
    def list_active_packages(session: Session) -> list[CoinPackage]:
        stmt = (
            select(CoinPackage)
            .where(CoinPackage.is_active.is_(True))
            .order_by(asc(CoinPackage.coin_amount))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def get_package(session: Session, package_id: int) -> CoinPackage | None:
        return session.get(CoinPackage, package_id)

    @staticmethod
    def create_bank_deposit_request(
        session: Session,
        user_id: int,
        package_id: int,
        receipt_file_id: str,
        receipt_file_type: str,
    ) -> DepositRequest:
        package = session.get(CoinPackage, package_id)
        if not package or not package.is_active:
            raise ValueError("Package not available")

        request = DepositRequest(
            user_id=user_id,
            package_id=package_id,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
            status=DEPOSIT_STATUS_PENDING,
        )
        session.add(request)
        session.flush()
        return request

    @staticmethod
    def list_pending_bank_requests(session: Session) -> list[DepositRequest]:
        stmt = (
            select(DepositRequest)
            .options(joinedload(DepositRequest.user), joinedload(DepositRequest.package))
            .where(DepositRequest.status == DEPOSIT_STATUS_PENDING)
            .order_by(asc(DepositRequest.id))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def approve_bank_request(session: Session, request_id: int, admin_id: int) -> DepositRequest:
        req = session.get(DepositRequest, request_id)
        if not req:
            raise ValueError("Deposit request not found")
        if req.status != DEPOSIT_STATUS_PENDING:
            raise ValueError("Deposit request is not pending")

        user = session.get(User, req.user_id)
        package = session.get(CoinPackage, req.package_id)
        if not user or not package:
            raise ValueError("Related user/package not found")

        user.coin_balance += package.coin_amount
        req.status = DEPOSIT_STATUS_APPROVED
        req.approved_by = admin_id

        AdminService.log_action(
            session,
            admin_id,
            "approve_bank_deposit",
            LOG_ENTITY_BANK_DEPOSIT,
            req.id,
            f"coins={package.coin_amount}; user_tg={user.telegram_id}",
        )

        session.flush()
        return req

    @staticmethod
    def reject_bank_request(session: Session, request_id: int, admin_id: int, note: str = "") -> DepositRequest:
        req = session.get(DepositRequest, request_id)
        if not req:
            raise ValueError("Deposit request not found")
        if req.status != DEPOSIT_STATUS_PENDING:
            raise ValueError("Deposit request is not pending")

        req.status = DEPOSIT_STATUS_REJECTED
        req.approved_by = admin_id
        req.admin_note = note or None

        AdminService.log_action(
            session,
            admin_id,
            "reject_bank_deposit",
            LOG_ENTITY_BANK_DEPOSIT,
            req.id,
            note or None,
        )

        session.flush()
        return req

    @staticmethod
    def create_crypto_deposit_request(
        session: Session,
        user_id: int,
        package_id: int,
        wallet_address: str,
    ) -> CryptoDepositRequest:
        package = session.get(CoinPackage, package_id)
        if not package or not package.is_active:
            raise ValueError("Package not available")
        if not wallet_address:
            raise ValueError("TRON_WALLET_ADDRESS is not configured")

        req = CryptoDepositRequest(
            user_id=user_id,
            package_id=package_id,
            expected_trx=package.trx_amount,
            wallet_address=wallet_address,
            status=CRYPTO_STATUS_PENDING_PAYMENT,
        )
        session.add(req)
        session.flush()
        return req

    @staticmethod
    def list_pending_crypto_requests(session: Session) -> list[CryptoDepositRequest]:
        stmt = (
            select(CryptoDepositRequest)
            .options(
                joinedload(CryptoDepositRequest.user),
                joinedload(CryptoDepositRequest.package),
            )
            .where(
                CryptoDepositRequest.status.in_(
                    [CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED]
                )
            )
            .order_by(asc(CryptoDepositRequest.id))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_open_crypto_requests_for_detection(session: Session) -> list[CryptoDepositRequest]:
        stmt = (
            select(CryptoDepositRequest)
            .where(CryptoDepositRequest.status == CRYPTO_STATUS_PENDING_PAYMENT)
            .order_by(asc(CryptoDepositRequest.id))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def known_tx_hashes(session: Session) -> set[str]:
        stmt = select(CryptoDepositRequest.tx_hash).where(CryptoDepositRequest.tx_hash.is_not(None))
        return {v for v in session.scalars(stmt).all() if v}

    @staticmethod
    def mark_crypto_detected(
        session: Session,
        request_id: int,
        tx_hash: str,
        from_address: str | None,
    ) -> CryptoDepositRequest:
        req = session.get(CryptoDepositRequest, request_id)
        if not req:
            raise ValueError("Crypto request not found")
        if req.status != CRYPTO_STATUS_PENDING_PAYMENT:
            raise ValueError("Crypto request is not pending for payment")

        req.tx_hash = tx_hash
        req.tx_from_address = from_address
        req.status = CRYPTO_STATUS_DETECTED
        req.detected_at = datetime.now(timezone.utc)
        session.flush()
        return req

    @staticmethod
    def approve_crypto_request(session: Session, request_id: int, admin_id: int) -> CryptoDepositRequest:
        req = session.get(CryptoDepositRequest, request_id)
        if not req:
            raise ValueError("Crypto request not found")
        if req.status not in {CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED}:
            raise ValueError("Crypto request not eligible for approval")

        if not req.tx_hash:
            raise ValueError("No transaction detected yet. Approval blocked.")

        user = session.get(User, req.user_id)
        package = session.get(CoinPackage, req.package_id)
        if not user or not package:
            raise ValueError("Related user/package not found")

        user.coin_balance += package.coin_amount
        req.status = CRYPTO_STATUS_APPROVED
        req.approved_by = admin_id

        AdminService.log_action(
            session,
            admin_id,
            "approve_crypto_deposit",
            LOG_ENTITY_CRYPTO_DEPOSIT,
            req.id,
            f"coins={package.coin_amount}; user_tg={user.telegram_id}; tx={req.tx_hash}",
        )

        session.flush()
        return req

    @staticmethod
    def reject_crypto_request(session: Session, request_id: int, admin_id: int, note: str = "") -> CryptoDepositRequest:
        req = session.get(CryptoDepositRequest, request_id)
        if not req:
            raise ValueError("Crypto request not found")
        if req.status in {CRYPTO_STATUS_APPROVED, CRYPTO_STATUS_REJECTED}:
            raise ValueError("Crypto request already finalized")

        req.status = CRYPTO_STATUS_REJECTED
        req.approved_by = admin_id
        req.admin_note = note or None

        AdminService.log_action(
            session,
            admin_id,
            "reject_crypto_deposit",
            LOG_ENTITY_CRYPTO_DEPOSIT,
            req.id,
            note or None,
        )

        session.flush()
        return req

    @staticmethod
    def find_matching_request_for_amount(
        requests: list[CryptoDepositRequest],
        amount_trx: Decimal,
        tx_timestamp_ms: int,
        tolerance: Decimal = Decimal("0.000001"),
    ) -> CryptoDepositRequest | None:
        for req in requests:
            expected = Decimal(req.expected_trx)
            if abs(expected - amount_trx) > tolerance:
                continue
            created_ms = int(req.created_at.timestamp() * 1000)
            if tx_timestamp_ms + 120000 < created_ms:
                continue
            return req
        return None

    @staticmethod
    def get_recent_crypto_requests(session: Session, limit: int = 200) -> list[CryptoDepositRequest]:
        stmt = (
            select(CryptoDepositRequest)
            .order_by(desc(CryptoDepositRequest.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_user_bank_deposits(
        session: Session,
        user_id: int,
        limit: int = 20,
    ) -> list[DepositRequest]:
        stmt = (
            select(DepositRequest)
            .options(joinedload(DepositRequest.package))
            .where(DepositRequest.user_id == user_id)
            .order_by(desc(DepositRequest.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_user_crypto_deposits(
        session: Session,
        user_id: int,
        limit: int = 20,
    ) -> list[CryptoDepositRequest]:
        stmt = (
            select(CryptoDepositRequest)
            .options(joinedload(CryptoDepositRequest.package))
            .where(CryptoDepositRequest.user_id == user_id)
            .order_by(desc(CryptoDepositRequest.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())
