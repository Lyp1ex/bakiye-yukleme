from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class CoinPackage(Base):
    __tablename__ = "coin_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    try_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    coin_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    trx_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    deposit_requests = relationship("DepositRequest", back_populates="package")
    crypto_deposit_requests = relationship("CryptoDepositRequest", back_populates="package")
