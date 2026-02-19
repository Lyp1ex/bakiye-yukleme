from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from bot.models import CryptoDepositRequest, DepositRequest, WithdrawalRequest


def _req_code(request_id: int) -> str:
    return f"DS-#{request_id}"


def _to_date(dt: datetime | None) -> date | None:
    if dt is None:
        return None
    return dt.date()


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class DailyFinanceReport:
    day: date
    bank_pending: int
    bank_approved_today: int
    bank_rejected_today: int
    bank_approved_try_total: float
    bank_approved_coin_total: int
    crypto_pending: int
    crypto_approved_today: int
    crypto_rejected_today: int
    crypto_approved_trx_total: float
    crypto_approved_coin_total: int
    withdraw_pending: int
    withdraw_completed_today: int
    withdraw_rejected_today: int
    withdraw_completed_coin_total: int


class ReportService:
    @staticmethod
    def build_daily_finance_report(session: Session, target_day: date | None = None) -> DailyFinanceReport:
        day = target_day or datetime.now(timezone.utc).date()

        bank_rows = list(
            session.scalars(
                select(DepositRequest).options(
                    joinedload(DepositRequest.user),
                    joinedload(DepositRequest.package),
                )
            ).all()
        )
        crypto_rows = list(
            session.scalars(
                select(CryptoDepositRequest).options(
                    joinedload(CryptoDepositRequest.user),
                    joinedload(CryptoDepositRequest.package),
                )
            ).all()
        )
        withdraw_rows = list(
            session.scalars(
                select(WithdrawalRequest).options(joinedload(WithdrawalRequest.user))
            ).all()
        )

        bank_pending = sum(1 for r in bank_rows if r.status == "pending")
        bank_approved_today_rows = [
            r for r in bank_rows if r.status == "approved" and _to_date(r.updated_at) == day
        ]
        bank_rejected_today = sum(
            1 for r in bank_rows if r.status == "rejected" and _to_date(r.updated_at) == day
        )
        bank_approved_try_total = float(
            sum(float(r.package.try_price) for r in bank_approved_today_rows if r.package)
        )
        bank_approved_coin_total = sum(int(r.package.coin_amount) for r in bank_approved_today_rows if r.package)

        crypto_pending = sum(1 for r in crypto_rows if r.status in {"pending_payment", "detected"})
        crypto_approved_today_rows = [
            r for r in crypto_rows if r.status == "approved" and _to_date(r.updated_at) == day
        ]
        crypto_rejected_today = sum(
            1 for r in crypto_rows if r.status == "rejected" and _to_date(r.updated_at) == day
        )
        crypto_approved_trx_total = float(sum(float(r.expected_trx) for r in crypto_approved_today_rows))
        crypto_approved_coin_total = sum(int(r.package.coin_amount) for r in crypto_approved_today_rows if r.package)

        withdraw_pending = sum(1 for r in withdraw_rows if r.status == "pending")
        withdraw_completed_today_rows = [
            r for r in withdraw_rows if r.status == "completed" and _to_date(r.updated_at) == day
        ]
        withdraw_rejected_today = sum(
            1 for r in withdraw_rows if r.status == "rejected" and _to_date(r.updated_at) == day
        )
        withdraw_completed_coin_total = sum(int(r.amount_coins) for r in withdraw_completed_today_rows)

        return DailyFinanceReport(
            day=day,
            bank_pending=bank_pending,
            bank_approved_today=len(bank_approved_today_rows),
            bank_rejected_today=bank_rejected_today,
            bank_approved_try_total=bank_approved_try_total,
            bank_approved_coin_total=bank_approved_coin_total,
            crypto_pending=crypto_pending,
            crypto_approved_today=len(crypto_approved_today_rows),
            crypto_rejected_today=crypto_rejected_today,
            crypto_approved_trx_total=crypto_approved_trx_total,
            crypto_approved_coin_total=crypto_approved_coin_total,
            withdraw_pending=withdraw_pending,
            withdraw_completed_today=len(withdraw_completed_today_rows),
            withdraw_rejected_today=withdraw_rejected_today,
            withdraw_completed_coin_total=withdraw_completed_coin_total,
        )

    @staticmethod
    def export_all_transactions_csv(session: Session) -> bytes:
        bank_rows = list(
            session.scalars(
                select(DepositRequest).options(
                    joinedload(DepositRequest.user),
                    joinedload(DepositRequest.package),
                )
            ).all()
        )
        crypto_rows = list(
            session.scalars(
                select(CryptoDepositRequest).options(
                    joinedload(CryptoDepositRequest.user),
                    joinedload(CryptoDepositRequest.package),
                )
            ).all()
        )
        withdraw_rows = list(
            session.scalars(
                select(WithdrawalRequest).options(joinedload(WithdrawalRequest.user))
            ).all()
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "islem_tipi",
                "talep_kodu",
                "telegram_id",
                "kullanici_adi",
                "durum",
                "tutar_bakiye",
                "tutar_tl",
                "tutar_trx",
                "iban",
                "banka",
                "tx_hash",
                "olusturma",
                "guncelleme",
            ]
        )

        for r in bank_rows:
            writer.writerow(
                [
                    "banka_yukleme",
                    _req_code(r.id),
                    r.user.telegram_id if r.user else "",
                    f"@{r.user.username}" if r.user and r.user.username else "",
                    r.status,
                    int(r.package.coin_amount) if r.package else "",
                    float(r.package.try_price) if r.package else "",
                    "",
                    "",
                    "",
                    "",
                    _fmt_dt(r.created_at),
                    _fmt_dt(r.updated_at),
                ]
            )

        for r in crypto_rows:
            writer.writerow(
                [
                    "kripto_yukleme",
                    _req_code(r.id),
                    r.user.telegram_id if r.user else "",
                    f"@{r.user.username}" if r.user and r.user.username else "",
                    r.status,
                    int(r.package.coin_amount) if r.package else "",
                    "",
                    float(r.expected_trx),
                    "",
                    "",
                    r.tx_hash or "",
                    _fmt_dt(r.created_at),
                    _fmt_dt(r.updated_at),
                ]
            )

        for r in withdraw_rows:
            writer.writerow(
                [
                    "cekim",
                    _req_code(r.id),
                    r.user.telegram_id if r.user else "",
                    f"@{r.user.username}" if r.user and r.user.username else "",
                    r.status,
                    int(r.amount_coins),
                    "",
                    "",
                    r.iban,
                    r.bank_name,
                    "",
                    _fmt_dt(r.created_at),
                    _fmt_dt(r.updated_at),
                ]
            )

        return output.getvalue().encode("utf-8")
