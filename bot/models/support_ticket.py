from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_request_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True, default="open")
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="support_tickets")

