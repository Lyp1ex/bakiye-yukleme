from __future__ import annotations

from decimal import Decimal


STATUS_MAP_TR = {
    "pending": "Beklemede",
    "approved": "Onaylandı",
    "rejected": "Reddedildi",
    "pending_payment": "Ödeme Bekleniyor",
    "detected": "Ödeme Tespit Edildi",
    "paid_waiting_proof": "SS Bekleniyor",
    "waiting_user_info": "Kullanıcı Bilgisi Bekleniyor",
    "pending_admin": "Admin İşleminde",
    "completed": "Tamamlandı",
    "cancelled": "İptal Edildi",
}


def fmt_try(value: Decimal | float | int) -> str:
    return f"{Decimal(value):,.2f} TL".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_trx(value: Decimal | float | int) -> str:
    return f"{Decimal(value):.6f} TRX"


def fmt_status(status: str) -> str:
    return STATUS_MAP_TR.get(status, status)
