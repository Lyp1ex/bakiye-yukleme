from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, joinedload

from bot.models import CoinPackage, CryptoDepositRequest, DepositRequest, ReceiptFingerprint, User
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
    def get_or_create_dynamic_package(
        session: Session,
        balance_amount: int,
        payment_try: Decimal,
    ) -> CoinPackage:
        payment_try = Decimal(payment_try).quantize(Decimal("0.01"))

        stmt = select(CoinPackage).where(
            CoinPackage.coin_amount == balance_amount,
            CoinPackage.try_price == payment_try,
        )
        pkg = session.scalar(stmt)
        if pkg:
            if not pkg.is_active:
                pkg.is_active = True
            return pkg

        pkg = CoinPackage(
            name=f"Bakiye Yükleme {balance_amount}",
            try_price=payment_try,
            coin_amount=balance_amount,
            trx_amount=Decimal("0.000001"),
            is_active=True,
        )
        session.add(pkg)
        session.flush()
        return pkg

    @staticmethod
    def count_pending_bank_requests_for_user(session: Session, user_id: int) -> int:
        return int(
            session.scalar(
                select(func.count(DepositRequest.id)).where(
                    DepositRequest.user_id == user_id,
                    DepositRequest.status == DEPOSIT_STATUS_PENDING,
                )
            )
            or 0
        )

    @staticmethod
    def count_recent_bank_requests_for_user(
        session: Session,
        user_id: int,
        minutes: int = 30,
    ) -> int:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=max(minutes, 1))
        return int(
            session.scalar(
                select(func.count(DepositRequest.id)).where(
                    DepositRequest.user_id == user_id,
                    DepositRequest.created_at >= threshold,
                )
            )
            or 0
        )

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
            raise ValueError("Paket uygun değil")

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
    def get_bank_queue_position(session: Session, request_id: int) -> tuple[int, int] | None:
        req = session.get(DepositRequest, request_id)
        if not req or req.status != DEPOSIT_STATUS_PENDING:
            return None

        total = int(
            session.scalar(
                select(func.count(DepositRequest.id)).where(
                    DepositRequest.status == DEPOSIT_STATUS_PENDING
                )
            )
            or 0
        )
        position = int(
            session.scalar(
                select(func.count(DepositRequest.id)).where(
                    DepositRequest.status == DEPOSIT_STATUS_PENDING,
                    DepositRequest.id <= request_id,
                )
            )
            or 0
        )
        return position, total

    @staticmethod
    def list_pending_bank_older_than(session: Session, minutes: int) -> list[DepositRequest]:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=max(minutes, 1))
        stmt = (
            select(DepositRequest)
            .options(joinedload(DepositRequest.user), joinedload(DepositRequest.package))
            .where(
                DepositRequest.status == DEPOSIT_STATUS_PENDING,
                DepositRequest.created_at <= threshold,
            )
            .order_by(asc(DepositRequest.id))
        )
        return list(session.scalars(stmt).all())

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
            raise ValueError("Yükleme talebi bulunamadı")
        if req.status != DEPOSIT_STATUS_PENDING:
            raise ValueError("Talep beklemede değil")

        user = session.get(User, req.user_id)
        package = session.get(CoinPackage, req.package_id)
        if not user or not package:
            raise ValueError("İlgili kullanıcı veya paket bulunamadı")

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
            raise ValueError("Yükleme talebi bulunamadı")
        if req.status != DEPOSIT_STATUS_PENDING:
            raise ValueError("Talep beklemede değil")

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
            raise ValueError("Paket uygun değil")
        if not wallet_address:
            raise ValueError("TRON cüzdan adresi ayarlanmamış")

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
    def get_crypto_queue_position(session: Session, request_id: int) -> tuple[int, int] | None:
        req = session.get(CryptoDepositRequest, request_id)
        if not req or req.status not in {CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED}:
            return None

        total = int(
            session.scalar(
                select(func.count(CryptoDepositRequest.id)).where(
                    CryptoDepositRequest.status.in_(
                        [CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED]
                    )
                )
            )
            or 0
        )
        position = int(
            session.scalar(
                select(func.count(CryptoDepositRequest.id)).where(
                    CryptoDepositRequest.status.in_(
                        [CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED]
                    ),
                    CryptoDepositRequest.id <= request_id,
                )
            )
            or 0
        )
        return position, total

    @staticmethod
    def list_pending_crypto_older_than(session: Session, minutes: int) -> list[CryptoDepositRequest]:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=max(minutes, 1))
        stmt = (
            select(CryptoDepositRequest)
            .options(joinedload(CryptoDepositRequest.user), joinedload(CryptoDepositRequest.package))
            .where(
                CryptoDepositRequest.status.in_([CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED]),
                CryptoDepositRequest.created_at <= threshold,
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
    def register_receipt_fingerprint(
        session: Session,
        user_id: int,
        file_sha256: str,
        deposit_request_id: int | None = None,
    ) -> tuple[ReceiptFingerprint, bool]:
        fingerprint = session.scalar(
            select(ReceiptFingerprint).where(ReceiptFingerprint.file_sha256 == file_sha256)
        )
        if fingerprint:
            fingerprint.seen_count += 1
            fingerprint.last_deposit_request_id = deposit_request_id
            fingerprint.last_seen_at = datetime.now(timezone.utc)
            session.flush()
            return fingerprint, True

        fingerprint = ReceiptFingerprint(
            file_sha256=file_sha256,
            user_id=user_id,
            first_deposit_request_id=deposit_request_id,
            last_deposit_request_id=deposit_request_id,
            seen_count=1,
        )
        session.add(fingerprint)
        session.flush()
        return fingerprint, False

    @staticmethod
    def find_receipt_fingerprint(session: Session, file_sha256: str) -> ReceiptFingerprint | None:
        return session.scalar(
            select(ReceiptFingerprint).where(ReceiptFingerprint.file_sha256 == file_sha256)
        )

    @staticmethod
    def mark_crypto_detected(
        session: Session,
        request_id: int,
        tx_hash: str,
        from_address: str | None,
    ) -> CryptoDepositRequest:
        req = session.get(CryptoDepositRequest, request_id)
        if not req:
            raise ValueError("Kripto talebi bulunamadı")
        if req.status != CRYPTO_STATUS_PENDING_PAYMENT:
            raise ValueError("Kripto talebi ödeme bekleme durumunda değil")

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
            raise ValueError("Kripto talebi bulunamadı")
        if req.status not in {CRYPTO_STATUS_PENDING_PAYMENT, CRYPTO_STATUS_DETECTED}:
            raise ValueError("Kripto talebi onaya uygun değil")

        if not req.tx_hash:
            raise ValueError("Henüz işlem tespit edilmedi. Onay engellendi.")

        user = session.get(User, req.user_id)
        package = session.get(CoinPackage, req.package_id)
        if not user or not package:
            raise ValueError("İlgili kullanıcı veya paket bulunamadı")

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
            raise ValueError("Kripto talebi bulunamadı")
        if req.status in {CRYPTO_STATUS_APPROVED, CRYPTO_STATUS_REJECTED}:
            raise ValueError("Kripto talebi zaten sonuçlandı")

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
    def count_recent_rejected_bank_for_user(session: Session, user_id: int, hours: int = 24) -> int:
        threshold = datetime.now(timezone.utc) - timedelta(hours=max(hours, 1))
        return int(
            session.scalar(
                select(func.count(DepositRequest.id)).where(
                    DepositRequest.user_id == user_id,
                    DepositRequest.status == DEPOSIT_STATUS_REJECTED,
                    DepositRequest.updated_at >= threshold,
                )
            )
            or 0
        )

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
