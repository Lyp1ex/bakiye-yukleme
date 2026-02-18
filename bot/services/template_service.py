from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import MessageTemplate


class TemplateService:
    @staticmethod
    def get_template(session: Session, key: str, fallback: str) -> str:
        row = session.scalar(select(MessageTemplate).where(MessageTemplate.key == key))
        if row and row.content.strip():
            return row.content
        return fallback

    @staticmethod
    def set_template(session: Session, key: str, content: str) -> MessageTemplate:
        row = session.scalar(select(MessageTemplate).where(MessageTemplate.key == key))
        if row:
            row.content = content
        else:
            row = MessageTemplate(key=key, content=content)
            session.add(row)
        session.flush()
        return row

    @staticmethod
    def list_templates(session: Session) -> list[MessageTemplate]:
        stmt = select(MessageTemplate).order_by(MessageTemplate.key.asc())
        return list(session.scalars(stmt).all())
