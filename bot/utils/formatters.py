from __future__ import annotations

from decimal import Decimal



def fmt_try(value: Decimal | float | int) -> str:
    return f"{Decimal(value):,.2f} TRY".replace(",", "_").replace(".", ",").replace("_", ".")



def fmt_trx(value: Decimal | float | int) -> str:
    return f"{Decimal(value):.6f} TRX"
