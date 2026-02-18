from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class DepositRequest(Base):
    __tablename__ = "deposit_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("coin_packages.id"), nullable=False)
    receipt_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    receipt_file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="photo")
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True, default="pending")
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="deposit_requests")
    package = relationship("CoinPackage", back_populates="deposit_requests")
