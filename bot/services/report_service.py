from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from bot.models import CryptoDepositRequest, DepositRequest, RiskFlag, SupportTicket, User, WithdrawalRequest


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


def _to_aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


@dataclass
class KpiDashboard:
    day: date
    total_users: int
    new_users_today: int
    active_users_24h: int
    total_coin_balance: int
    highest_balance_telegram_id: int | None
    highest_balance_amount: int
    bank_pending: int
    crypto_pending: int
    withdraw_pending: int
    open_tickets: int
    open_risk_flags: int
    bank_approved_today: int
    bank_rejected_today: int
    bank_approval_rate_today: float
    bank_approved_try_today: float
    withdraw_completed_today: int
    withdraw_rejected_today: int
    withdraw_success_rate_today: float
    withdraw_completed_coin_today: int


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
    def build_kpi_dashboard(session: Session, target_day: date | None = None) -> KpiDashboard:
        day = target_day or datetime.now(timezone.utc).date()

        users = list(session.scalars(select(User)).all())
        bank_rows = list(
            session.scalars(select(DepositRequest).options(joinedload(DepositRequest.package))).all()
        )
        crypto_rows = list(session.scalars(select(CryptoDepositRequest)).all())
        withdraw_rows = list(session.scalars(select(WithdrawalRequest)).all())
        tickets = list(session.scalars(select(SupportTicket)).all())
        risks = list(session.scalars(select(RiskFlag)).all())

        total_users = len(users)
        new_users_today = sum(1 for u in users if _to_date(u.created_at) == day)
        total_coin_balance = sum(int(u.coin_balance) for u in users)
        highest = max(users, key=lambda u: int(u.coin_balance), default=None)

        bank_pending = sum(1 for r in bank_rows if r.status == "pending")
        crypto_pending = sum(1 for r in crypto_rows if r.status in {"pending_payment", "detected"})
        withdraw_pending = sum(1 for r in withdraw_rows if r.status == "pending")
        open_tickets = sum(1 for t in tickets if t.status == "open")
        open_risk_flags = sum(1 for r in risks if not r.is_resolved)

        bank_approved_today_rows = [
            r for r in bank_rows if r.status == "approved" and _to_date(r.updated_at) == day
        ]
        bank_rejected_today_rows = [
            r for r in bank_rows if r.status == "rejected" and _to_date(r.updated_at) == day
        ]
        bank_total_decisions = len(bank_approved_today_rows) + len(bank_rejected_today_rows)
        bank_approval_rate = (
            (len(bank_approved_today_rows) / bank_total_decisions) * 100 if bank_total_decisions > 0 else 0.0
        )
        bank_approved_try_today = float(
            sum(float(r.package.try_price) for r in bank_approved_today_rows if r.package)
        )

        withdraw_completed_today_rows = [
            r for r in withdraw_rows if r.status == "completed" and _to_date(r.updated_at) == day
        ]
        withdraw_rejected_today_rows = [
            r for r in withdraw_rows if r.status == "rejected" and _to_date(r.updated_at) == day
        ]
        withdraw_total_decisions = len(withdraw_completed_today_rows) + len(withdraw_rejected_today_rows)
        withdraw_success_rate = (
            (len(withdraw_completed_today_rows) / withdraw_total_decisions) * 100
            if withdraw_total_decisions > 0
            else 0.0
        )
        withdraw_completed_coin_today = sum(int(r.amount_coins) for r in withdraw_completed_today_rows)

        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)
        active_user_ids: set[int] = set()
        for row in bank_rows:
            created_at = _to_aware_utc(row.created_at)
            if row.user_id and created_at and created_at >= since:
                active_user_ids.add(row.user_id)
        for row in crypto_rows:
            created_at = _to_aware_utc(row.created_at)
            if row.user_id and created_at and created_at >= since:
                active_user_ids.add(row.user_id)
        for row in withdraw_rows:
            created_at = _to_aware_utc(row.created_at)
            if row.user_id and created_at and created_at >= since:
                active_user_ids.add(row.user_id)
        for row in tickets:
            created_at = _to_aware_utc(row.created_at)
            if row.user_id and created_at and created_at >= since:
                active_user_ids.add(row.user_id)

        return KpiDashboard(
            day=day,
            total_users=total_users,
            new_users_today=new_users_today,
            active_users_24h=len(active_user_ids),
            total_coin_balance=total_coin_balance,
            highest_balance_telegram_id=highest.telegram_id if highest else None,
            highest_balance_amount=int(highest.coin_balance) if highest else 0,
            bank_pending=bank_pending,
            crypto_pending=crypto_pending,
            withdraw_pending=withdraw_pending,
            open_tickets=open_tickets,
            open_risk_flags=open_risk_flags,
            bank_approved_today=len(bank_approved_today_rows),
            bank_rejected_today=len(bank_rejected_today_rows),
            bank_approval_rate_today=bank_approval_rate,
            bank_approved_try_today=bank_approved_try_today,
            withdraw_completed_today=len(withdraw_completed_today_rows),
            withdraw_rejected_today=len(withdraw_rejected_today_rows),
            withdraw_success_rate_today=withdraw_success_rate,
            withdraw_completed_coin_today=withdraw_completed_coin_today,
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
