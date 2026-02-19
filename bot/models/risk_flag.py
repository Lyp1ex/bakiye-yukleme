from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="risk_flags")

