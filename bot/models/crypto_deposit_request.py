from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class CryptoDepositRequest(Base):
    __tablename__ = "crypto_deposit_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("coin_packages.id"), nullable=False)
    expected_trx: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(128), nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    tx_from_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, default="pending_payment"
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detected_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="crypto_deposit_requests")
    package = relationship("CoinPackage", back_populates="crypto_deposit_requests")
