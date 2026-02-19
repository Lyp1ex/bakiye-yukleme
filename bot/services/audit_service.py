from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from bot.models import AdminLog


class AuditService:
    @staticmethod
    def log_user_action(
        session: Session,
        user_telegram_id: int,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        details: str | None = None,
    ) -> None:
        session.add(
            AdminLog(
                admin_telegram_id=user_telegram_id,
                action=f"user:{action}",
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        )

    @staticmethod
    def log_system_action(
        session: Session,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        details: str | None = None,
    ) -> None:
        session.add(
            AdminLog(
                admin_telegram_id=0,
                action=f"system:{action}",
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
            )
        )

    @staticmethod
    def list_recent(session: Session, limit: int = 40) -> list[AdminLog]:
        return list(
            session.scalars(
                select(AdminLog).order_by(desc(AdminLog.id)).limit(max(limit, 1))
            ).all()
        )

    @staticmethod
    def actor_text(log: AdminLog) -> str:
        if log.action.startswith("user:"):
            return f"Kullanıcı({log.admin_telegram_id})"
        if log.action.startswith("system:"):
            return "Sistem"
        return f"Admin({log.admin_telegram_id})"
