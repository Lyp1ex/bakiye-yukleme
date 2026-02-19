from __future__ import annotations

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session, joinedload

from bot.models import Game, Order, Product, User
from bot.services.admin_service import AdminService
from bot.utils.constants import (
    LOG_ENTITY_ORDER,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_PENDING_ADMIN,
    ORDER_STATUS_WAITING_INFO,
)


class ShopService:
    @staticmethod
    def list_active_games(session: Session) -> list[Game]:
        stmt = select(Game).where(Game.is_active.is_(True)).order_by(asc(Game.name))
        return list(session.scalars(stmt).all())

    @staticmethod
    def get_game(session: Session, game_id: int) -> Game | None:
        return session.get(Game, game_id)

    @staticmethod
    def list_active_products_by_game(session: Session, game_id: int) -> list[Product]:
        stmt = (
            select(Product)
            .where(Product.game_id == game_id, Product.is_active.is_(True))
            .order_by(asc(Product.price_coins))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def get_product(session: Session, product_id: int) -> Product | None:
        return session.get(Product, product_id)

    @staticmethod
    def create_order_with_coin_deduction(session: Session, user_id: int, product_id: int) -> Order:
        user = session.get(User, user_id)
        product = session.get(Product, product_id)
        if not user or not product or not product.is_active:
            raise ValueError("Ürün uygun değil")

        if user.coin_balance < product.price_coins:
            raise ValueError("Coin bakiyesi yetersiz")

        user.coin_balance -= product.price_coins

        order = Order(
            user_id=user_id,
            product_id=product_id,
            status=ORDER_STATUS_WAITING_INFO,
        )
        session.add(order)
        session.flush()
        return order

    @staticmethod
    def attach_delivery_info(
        session: Session,
        order_id: int,
        game_user_id: str,
        iban: str,
        full_name: str,
        bank_name: str,
    ) -> Order:
        order = session.get(Order, order_id)
        if not order:
            raise ValueError("Sipariş bulunamadı")
        if order.status != ORDER_STATUS_WAITING_INFO:
            raise ValueError("Sipariş kullanıcı bilgisi bekleme durumunda değil")

        order.game_user_id = game_user_id.strip()
        order.iban = iban.strip()
        order.full_name = full_name.strip()
        order.bank_name = bank_name.strip()
        order.status = ORDER_STATUS_PENDING_ADMIN
        session.flush()
        return order

    @staticmethod
    def list_user_orders(session: Session, user_id: int, pending_only: bool = False) -> list[Order]:
        stmt = (
            select(Order)
            .options(joinedload(Order.product).joinedload(Product.game))
            .where(Order.user_id == user_id)
        )
        if pending_only:
            stmt = stmt.where(Order.status != ORDER_STATUS_COMPLETED)
        stmt = stmt.order_by(desc(Order.id)).limit(20)
        return list(session.scalars(stmt).all())

    @staticmethod
    def list_pending_orders(session: Session) -> list[Order]:
        stmt = (
            select(Order)
            .options(joinedload(Order.product).joinedload(Product.game), joinedload(Order.user))
            .where(Order.status == ORDER_STATUS_PENDING_ADMIN)
            .order_by(asc(Order.id))
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def complete_order(
        session: Session,
        order_id: int,
        admin_telegram_id: int,
        note: str = "",
    ) -> Order:
        order = session.get(Order, order_id)
        if not order:
            raise ValueError("Sipariş bulunamadı")
        if order.status != ORDER_STATUS_PENDING_ADMIN:
            raise ValueError("Sipariş admin onayı bekleme durumunda değil")

        order.status = ORDER_STATUS_COMPLETED
        order.completed_by = admin_telegram_id
        order.admin_note = note or None

        AdminService.log_action(
            session,
            admin_telegram_id,
            "complete_order",
            LOG_ENTITY_ORDER,
            order.id,
            note or None,
        )

        session.flush()
        return order
