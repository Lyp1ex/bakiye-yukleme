from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import asc, desc, distinct, func, select
from sqlalchemy.orm import Session, joinedload

from bot.models import RiskFlag, WithdrawalRequest
from bot.services.admin_service import AdminService
from bot.utils.constants import LOG_ENTITY_RISK


class RiskService:
    @staticmethod
    def create_flag(
        session: Session,
        user_id: int,
        score: int,
        source: str,
        reason: str,
        *,
        details: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        dedupe: bool = True,
    ) -> RiskFlag:
        safe_score = max(0, min(int(score), 100))

        if dedupe:
            existing = session.scalar(
                select(RiskFlag).where(
                    RiskFlag.user_id == user_id,
                    RiskFlag.source == source,
                    RiskFlag.entity_type == entity_type,
                    RiskFlag.entity_id == entity_id,
                    RiskFlag.reason == reason,
                    RiskFlag.is_resolved.is_(False),
                )
            )
            if existing:
                if details:
                    existing.details = details
                existing.score = max(existing.score, safe_score)
                session.flush()
                return existing

        flag = RiskFlag(
            user_id=user_id,
            score=safe_score,
            source=source,
            reason=reason,
            details=details,
            entity_type=entity_type,
            entity_id=entity_id,
            is_resolved=False,
        )
        session.add(flag)
        session.flush()
        return flag

    @staticmethod
    def list_open_flags(session: Session, limit: int = 50) -> list[RiskFlag]:
        stmt = (
            select(RiskFlag)
            .options(joinedload(RiskFlag.user))
            .where(RiskFlag.is_resolved.is_(False))
            .order_by(desc(RiskFlag.score), asc(RiskFlag.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def get_blocking_open_flag(
        session: Session,
        user_id: int,
        threshold: int,
    ) -> RiskFlag | None:
        stmt = (
            select(RiskFlag)
            .where(
                RiskFlag.user_id == user_id,
                RiskFlag.is_resolved.is_(False),
                RiskFlag.score >= max(int(threshold), 0),
            )
            .order_by(desc(RiskFlag.score), asc(RiskFlag.id))
            .limit(1)
        )
        return session.scalar(stmt)

    @staticmethod
    def resolve_flag(
        session: Session,
        flag_id: int,
        admin_id: int,
        note: str = "",
    ) -> RiskFlag:
        flag = session.get(RiskFlag, flag_id)
        if not flag:
            raise ValueError("Risk kaydı bulunamadı")
        if flag.is_resolved:
            raise ValueError("Risk kaydı zaten kapatılmış")

        flag.is_resolved = True
        flag.resolved_by = admin_id
        flag.resolved_at = datetime.now(timezone.utc)
        if note:
            if flag.details:
                flag.details = f"{flag.details}\nÇözüm Notu: {note}"
            else:
                flag.details = f"Çözüm Notu: {note}"

        AdminService.log_action(
            session,
            admin_id,
            "resolve_risk_flag",
            LOG_ENTITY_RISK,
            flag.id,
            f"source={flag.source}; user_id={flag.user_id}",
        )
        session.flush()
        return flag

    @staticmethod
    def flag_reused_iban_if_needed(
        session: Session,
        user_id: int,
        iban: str,
        withdrawal_request_id: int,
    ) -> RiskFlag | None:
        other_user_count = int(
            session.scalar(
                select(func.count(distinct(WithdrawalRequest.user_id))).where(
                    WithdrawalRequest.iban == iban,
                    WithdrawalRequest.user_id != user_id,
                )
            )
            or 0
        )
        if other_user_count <= 0:
            return None

        return RiskService.create_flag(
            session,
            user_id=user_id,
            score=85,
            source="iban_reuse",
            reason="Bu IBAN daha önce farklı kullanıcı(lar) tarafından da kullanıldı.",
            details=f"iban={iban}; baska_kullanici_sayisi={other_user_count}",
            entity_type="withdrawal",
            entity_id=withdrawal_request_id,
        )
