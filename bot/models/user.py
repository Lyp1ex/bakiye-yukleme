from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coin_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deposit_requests = relationship("DepositRequest", back_populates="user")
    crypto_deposit_requests = relationship("CryptoDepositRequest", back_populates="user")
    orders = relationship("Order", back_populates="user")
    withdrawal_requests = relationship("WithdrawalRequest", back_populates="user")
    risk_flags = relationship("RiskFlag", back_populates="user")
    support_tickets = relationship("SupportTicket", back_populates="user")
