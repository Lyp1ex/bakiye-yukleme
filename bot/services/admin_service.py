from __future__ import annotations

from decimal import Decimal

from sqlalchemy import asc, desc, or_, select
from sqlalchemy.orm import Session

from bot.models import AdminLog, CoinPackage, Game, MessageTemplate, Product, User
from bot.utils.constants import (
    LOG_ENTITY_COIN_PACKAGE,
    LOG_ENTITY_GAME,
    LOG_ENTITY_PRODUCT,
    LOG_ENTITY_TEMPLATE,
    LOG_ENTITY_USER,
)


class AdminService:
    @staticmethod
    def log_action(
        session: Session,
        admin_telegram_id: int,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        details: str | None = None,
    ) -> None:
        log = AdminLog(
            admin_telegram_id=admin_telegram_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        session.add(log)

    @staticmethod
    def list_games(session: Session) -> list[Game]:
        return list(session.scalars(select(Game).order_by(asc(Game.id))).all())

    @staticmethod
    def create_game(
        session: Session,
        admin_id: int,
        name: str,
        requires_server: bool,
        id_label: str,
    ) -> Game:
        game = Game(name=name, requires_server=requires_server, id_label=id_label)
        session.add(game)
        session.flush()
        AdminService.log_action(
            session,
            admin_id,
            "create_game",
            LOG_ENTITY_GAME,
            game.id,
            f"name={name}",
        )
        return game

    @staticmethod
    def toggle_game(session: Session, admin_id: int, game_id: int) -> Game:
        game = session.get(Game, game_id)
        if not game:
            raise ValueError("Oyun bulunamadı")
        game.is_active = not game.is_active
        AdminService.log_action(
            session,
            admin_id,
            "toggle_game",
            LOG_ENTITY_GAME,
            game.id,
            f"is_active={game.is_active}",
        )
        return game

    @staticmethod
    def list_products(session: Session) -> list[Product]:
        stmt = select(Product).order_by(asc(Product.id))
        return list(session.scalars(stmt).all())

    @staticmethod
    def create_product(
        session: Session,
        admin_id: int,
        game_id: int,
        name: str,
        description: str,
        price_coins: int,
    ) -> Product:
        game = session.get(Game, game_id)
        if not game:
            raise ValueError("Oyun bulunamadı")

        product = Product(
            game_id=game_id,
            name=name,
            description=description,
            price_coins=price_coins,
            is_active=True,
        )
        session.add(product)
        session.flush()
        AdminService.log_action(
            session,
            admin_id,
            "create_product",
            LOG_ENTITY_PRODUCT,
            product.id,
            f"name={name}",
        )
        return product

    @staticmethod
    def toggle_product(session: Session, admin_id: int, product_id: int) -> Product:
        product = session.get(Product, product_id)
        if not product:
            raise ValueError("Ürün bulunamadı")
        product.is_active = not product.is_active
        AdminService.log_action(
            session,
            admin_id,
            "toggle_product",
            LOG_ENTITY_PRODUCT,
            product.id,
            f"is_active={product.is_active}",
        )
        return product

    @staticmethod
    def list_coin_packages(session: Session) -> list[CoinPackage]:
        return list(session.scalars(select(CoinPackage).order_by(asc(CoinPackage.id))).all())

    @staticmethod
    def create_coin_package(
        session: Session,
        admin_id: int,
        name: str,
        try_price: Decimal,
        coin_amount: int,
        trx_amount: Decimal,
    ) -> CoinPackage:
        package = CoinPackage(
            name=name,
            try_price=try_price,
            coin_amount=coin_amount,
            trx_amount=trx_amount,
            is_active=True,
        )
        session.add(package)
        session.flush()
        AdminService.log_action(
            session,
            admin_id,
            "create_coin_package",
            LOG_ENTITY_COIN_PACKAGE,
            package.id,
            f"name={name}",
        )
        return package

    @staticmethod
    def toggle_coin_package(session: Session, admin_id: int, package_id: int) -> CoinPackage:
        package = session.get(CoinPackage, package_id)
        if not package:
            raise ValueError("Paket bulunamadı")
        package.is_active = not package.is_active
        AdminService.log_action(
            session,
            admin_id,
            "toggle_coin_package",
            LOG_ENTITY_COIN_PACKAGE,
            package.id,
            f"is_active={package.is_active}",
        )
        return package

    @staticmethod
    def search_users(session: Session, query: str) -> list[User]:
        query = query.strip()
        if not query:
            return []

        if query.isdigit():
            stmt = select(User).where(User.telegram_id == int(query))
            return list(session.scalars(stmt).all())

        stmt = select(User).where(
            or_(
                User.username.ilike(f"%{query}%"),
            )
        )
        return list(session.scalars(stmt).all())

    @staticmethod
    def manual_coin_adjust(
        session: Session,
        admin_id: int,
        telegram_id: int,
        delta: int,
        reason: str,
    ) -> User:
        user = session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            raise ValueError("Kullanıcı bulunamadı")
        new_balance = user.coin_balance + delta
        if new_balance < 0:
            raise ValueError("Düşme işlemi için bakiye yetersiz")
        user.coin_balance = new_balance
        AdminService.log_action(
            session,
            admin_id,
            "manual_coin_adjust",
            LOG_ENTITY_USER,
            user.id,
            f"delta={delta}; reason={reason}",
        )
        return user

    @staticmethod
    def list_templates(session: Session) -> list[MessageTemplate]:
        return list(session.scalars(select(MessageTemplate).order_by(asc(MessageTemplate.key))).all())

    @staticmethod
    def upsert_template(
        session: Session,
        admin_id: int,
        key: str,
        content: str,
    ) -> MessageTemplate:
        tpl = session.scalar(select(MessageTemplate).where(MessageTemplate.key == key))
        action = "update_template"
        if not tpl:
            tpl = MessageTemplate(key=key, content=content)
            session.add(tpl)
            action = "create_template"
        else:
            tpl.content = content
        session.flush()
        AdminService.log_action(
            session,
            admin_id,
            action,
            LOG_ENTITY_TEMPLATE,
            tpl.id,
            f"key={key}",
        )
        return tpl

    @staticmethod
    def get_user_with_highest_balance(session: Session) -> User | None:
        stmt = select(User).order_by(desc(User.coin_balance)).limit(1)
        return session.scalar(stmt)
