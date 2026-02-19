from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class ReceiptFingerprint(Base):
    __tablename__ = "receipt_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    first_deposit_request_id: Mapped[int | None] = mapped_column(ForeignKey("deposit_requests.id"), nullable=True)
    last_deposit_request_id: Mapped[int | None] = mapped_column(ForeignKey("deposit_requests.id"), nullable=True)
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User")

