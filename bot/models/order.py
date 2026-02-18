from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    game_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(80), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="waiting_user_info", index=True
    )
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
