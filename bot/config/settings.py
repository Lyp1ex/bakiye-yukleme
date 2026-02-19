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
    tron_rpc_url: str
    tron_wallet_address: str
    tron_private_key: str
    crypto_auto_approve: bool
    database_url: str
    log_level: str
    tron_check_interval_sec: int
    min_balance_amount: int
    max_balance_amount: int
    balance_payment_rate: Decimal



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
        tron_rpc_url=os.getenv("TRON_RPC_URL", "https://api.trongrid.io").rstrip("/"),
        tron_wallet_address=os.getenv("TRON_WALLET_ADDRESS", "").strip(),
        tron_private_key=os.getenv("TRON_PRIVATE_KEY", "").strip(),
        crypto_auto_approve=_parse_bool(os.getenv("CRYPTO_AUTO_APPROVE", "false")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./bot.db").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        tron_check_interval_sec=_parse_int(os.getenv("TRON_CHECK_INTERVAL_SEC"), 45),
        min_balance_amount=_parse_int(os.getenv("MIN_BALANCE_AMOUNT"), 15000),
        max_balance_amount=_parse_int(os.getenv("MAX_BALANCE_AMOUNT"), 250000),
        balance_payment_rate=_parse_decimal(
            os.getenv("BALANCE_PAYMENT_RATE"),
            Decimal("0.20"),
        ),
    )
