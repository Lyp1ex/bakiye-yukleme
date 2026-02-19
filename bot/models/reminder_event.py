from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class ReminderEvent(Base):
    __tablename__ = "reminder_events"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_reminder_events_entity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_sent_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

