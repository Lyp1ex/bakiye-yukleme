from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session, joinedload

from bot.models import SupportTicket
from bot.services.admin_service import AdminService
from bot.utils.constants import LOG_ENTITY_SUPPORT_TICKET

TICKET_STATUS_OPEN = "open"
TICKET_STATUS_RESOLVED = "resolved"
TICKET_STATUS_REJECTED = "rejected"


class TicketService:
    @staticmethod
    def create_ticket(
        session: Session,
        user_id: int,
        source_type: str,
        source_request_id: int,
        message: str,
    ) -> SupportTicket:
        clean_message = message.strip()
        if len(clean_message) < 5:
            raise ValueError("İtiraz mesajı çok kısa.")

        existing_open = session.scalar(
            select(SupportTicket).where(
                SupportTicket.user_id == user_id,
                SupportTicket.source_type == source_type,
                SupportTicket.source_request_id == source_request_id,
                SupportTicket.status == TICKET_STATUS_OPEN,
            )
        )
        if existing_open:
            raise ValueError("Bu talep için zaten açık bir itiraz kaydı var.")

        ticket = SupportTicket(
            user_id=user_id,
            source_type=source_type,
            source_request_id=source_request_id,
            message=clean_message,
            status=TICKET_STATUS_OPEN,
        )
        session.add(ticket)
        session.flush()
        return ticket

    @staticmethod
    def list_open_tickets(session: Session, limit: int = 50) -> list[SupportTicket]:
        stmt = (
            select(SupportTicket)
            .options(joinedload(SupportTicket.user))
            .where(SupportTicket.status == TICKET_STATUS_OPEN)
            .order_by(asc(SupportTicket.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_user_tickets(session: Session, user_id: int, limit: int = 20) -> list[SupportTicket]:
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id)
            .order_by(desc(SupportTicket.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def resolve_ticket(
        session: Session,
        ticket_id: int,
        admin_id: int,
        note: str = "",
    ) -> SupportTicket:
        ticket = session.get(SupportTicket, ticket_id)
        if not ticket:
            raise ValueError("İtiraz kaydı bulunamadı")
        if ticket.status != TICKET_STATUS_OPEN:
            raise ValueError("İtiraz kaydı kapatılmış durumda")

        ticket.status = TICKET_STATUS_RESOLVED
        ticket.admin_note = note or "İtiraz kabul edildi."
        ticket.resolved_by = admin_id
        ticket.resolved_at = datetime.now(timezone.utc)

        AdminService.log_action(
            session,
            admin_id,
            "resolve_support_ticket",
            LOG_ENTITY_SUPPORT_TICKET,
            ticket.id,
            f"source={ticket.source_type}; request_id={ticket.source_request_id}",
        )
        session.flush()
        return ticket

    @staticmethod
    def reject_ticket(
        session: Session,
        ticket_id: int,
        admin_id: int,
        note: str = "",
    ) -> SupportTicket:
        ticket = session.get(SupportTicket, ticket_id)
        if not ticket:
            raise ValueError("İtiraz kaydı bulunamadı")
        if ticket.status != TICKET_STATUS_OPEN:
            raise ValueError("İtiraz kaydı kapatılmış durumda")

        ticket.status = TICKET_STATUS_REJECTED
        ticket.admin_note = note or "İtiraz reddedildi."
        ticket.resolved_by = admin_id
        ticket.resolved_at = datetime.now(timezone.utc)

        AdminService.log_action(
            session,
            admin_id,
            "reject_support_ticket",
            LOG_ENTITY_SUPPORT_TICKET,
            ticket.id,
            f"source={ticket.source_type}; request_id={ticket.source_request_id}",
        )
        session.flush()
        return ticket

