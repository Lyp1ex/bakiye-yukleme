from __future__ import annotations

from telegram import User as TgUser
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from bot.models import Order, User


class UserService:
    @staticmethod
    def get_or_create_user(session: Session, tg_user: TgUser) -> User:
        stmt = select(User).where(User.telegram_id == tg_user.id)
        user = session.scalar(stmt)
        if user:
            if user.username != tg_user.username:
                user.username = tg_user.username
            return user

        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            coin_balance=0,
        )
        session.add(user)
        session.flush()
        return user

    @staticmethod
    def get_by_telegram_id(session: Session, telegram_id: int) -> User | None:
        return session.scalar(select(User).where(User.telegram_id == telegram_id))

    @staticmethod
    def list_recent_orders(session: Session, user_id: int, limit: int = 10) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(desc(Order.id))
            .limit(limit)
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def adjust_balance(session: Session, user_id: int, delta: int) -> int:
        user = session.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        new_balance = user.coin_balance + delta
        if new_balance < 0:
            raise ValueError("Insufficient balance")
        user.coin_balance = new_balance
        session.flush()
        return user.coin_balance
