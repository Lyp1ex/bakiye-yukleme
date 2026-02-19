from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class RequestStatusCard(Base):
    __tablename__ = "request_status_cards"
    __table_args__ = (
        UniqueConstraint("flow_type", "request_id", name="uq_request_status_cards_flow_request"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    flow_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    request_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    request_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    current_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    timeline_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_sla_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="request_status_cards")
