from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
import os
from typing import Set

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: Set[int]
    admin_panel_token: str
    iban_text: str
    support_username: str
    app_last_updated: str
    tron_rpc_url: str
    tron_wallet_address: str
    tron_private_key: str
    crypto_auto_approve: bool
    receipt_ai_provider: str
    openai_model: str
    openai_api_key: str
    gemini_api_key: str
    gemini_model: str
    receipt_ai_enabled: bool
    receipt_ai_strict: bool
    receipt_amount_tolerance_try: Decimal
    receipt_date_max_diff_days: int
    receipt_hash_check_enabled: bool
    receipt_risk_reject_threshold: int
    risk_flag_threshold: int
    database_url: str
    log_level: str
    tron_check_interval_sec: int
    min_balance_amount: int
    max_balance_amount: int
    balance_payment_rate: Decimal
    bank_queue_eta_min_per_request: int
    crypto_queue_eta_min_per_request: int
    withdraw_queue_eta_min_per_request: int
    reminder_enabled: bool
    reminder_interval_sec: int
    reminder_min_age_minutes: int
    reminder_cooldown_minutes: int
    auto_backup_enabled: bool
    backup_hour_utc: int
    backup_minute_utc: int
    backup_retention_days: int
    backup_dir: str



def _parse_admin_ids(raw: str) -> Set[int]:
    values: Set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.add(int(part))
        except ValueError:
            continue
    return values



def _parse_bool(raw: str, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}



def _parse_int(raw: str | None, default: int) -> int:
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default



def _parse_decimal(raw: str | None, default: Decimal) -> Decimal:
    if not raw:
        return default
    try:
        return Decimal(raw)
    except Exception:
        return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        admin_panel_token=os.getenv("ADMIN_PANEL_TOKEN", "").strip(),
        iban_text=os.getenv(
            "IBAN_TEXT",
            "IBAN: TR00 0000 0000 0000 0000 0000 00\\nAlıcı: Hesap Sahibi",
        ),
        support_username=os.getenv("SUPPORT_USERNAME", "donsalvatoree").strip().lstrip("@"),
        app_last_updated=os.getenv("APP_LAST_UPDATED", "19.02.2026").strip(),
        tron_rpc_url=os.getenv("TRON_RPC_URL", "https://api.trongrid.io").rstrip("/"),
        tron_wallet_address=os.getenv("TRON_WALLET_ADDRESS", "").strip(),
        tron_private_key=os.getenv("TRON_PRIVATE_KEY", "").strip(),
        crypto_auto_approve=_parse_bool(os.getenv("CRYPTO_AUTO_APPROVE", "false")),
        receipt_ai_provider=os.getenv("RECEIPT_AI_PROVIDER", "auto").strip().lower(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip(),
        receipt_ai_enabled=_parse_bool(os.getenv("RECEIPT_AI_ENABLED", "false")),
        receipt_ai_strict=_parse_bool(os.getenv("RECEIPT_AI_STRICT", "false")),
        receipt_amount_tolerance_try=_parse_decimal(
            os.getenv("RECEIPT_AMOUNT_TOLERANCE_TRY"),
            Decimal("5.00"),
        ),
        receipt_date_max_diff_days=_parse_int(os.getenv("RECEIPT_DATE_MAX_DIFF_DAYS"), 3),
        receipt_hash_check_enabled=_parse_bool(os.getenv("RECEIPT_HASH_CHECK_ENABLED", "true")),
        receipt_risk_reject_threshold=_parse_int(os.getenv("RECEIPT_RISK_REJECT_THRESHOLD"), 70),
        risk_flag_threshold=_parse_int(os.getenv("RISK_FLAG_THRESHOLD"), 40),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./bot.db").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        tron_check_interval_sec=_parse_int(os.getenv("TRON_CHECK_INTERVAL_SEC"), 45),
        min_balance_amount=_parse_int(os.getenv("MIN_BALANCE_AMOUNT"), 15000),
        max_balance_amount=_parse_int(os.getenv("MAX_BALANCE_AMOUNT"), 250000),
        balance_payment_rate=_parse_decimal(
            os.getenv("BALANCE_PAYMENT_RATE"),
            Decimal("0.20"),
        ),
        bank_queue_eta_min_per_request=_parse_int(os.getenv("BANK_QUEUE_ETA_MIN_PER_REQUEST"), 7),
        crypto_queue_eta_min_per_request=_parse_int(os.getenv("CRYPTO_QUEUE_ETA_MIN_PER_REQUEST"), 5),
        withdraw_queue_eta_min_per_request=_parse_int(os.getenv("WITHDRAW_QUEUE_ETA_MIN_PER_REQUEST"), 12),
        reminder_enabled=_parse_bool(os.getenv("REMINDER_ENABLED", "true")),
        reminder_interval_sec=_parse_int(os.getenv("REMINDER_INTERVAL_SEC"), 1800),
        reminder_min_age_minutes=_parse_int(os.getenv("REMINDER_MIN_AGE_MINUTES"), 20),
        reminder_cooldown_minutes=_parse_int(os.getenv("REMINDER_COOLDOWN_MINUTES"), 60),
        auto_backup_enabled=_parse_bool(os.getenv("AUTO_BACKUP_ENABLED", "true")),
        backup_hour_utc=_parse_int(os.getenv("BACKUP_HOUR_UTC"), 3),
        backup_minute_utc=_parse_int(os.getenv("BACKUP_MINUTE_UTC"), 15),
        backup_retention_days=_parse_int(os.getenv("BACKUP_RETENTION_DAYS"), 14),
        backup_dir=os.getenv("BACKUP_DIR", "./backups").strip(),
    )
