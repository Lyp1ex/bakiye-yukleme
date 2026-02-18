from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from bot.database.base import Base
from bot.database.session import engine, session_scope
from bot.models import CoinPackage, Game, MessageTemplate


DEFAULT_PACKAGES = [
    {"name": "Starter", "try_price": Decimal("100.00"), "coin_amount": 100, "trx_amount": Decimal("10.000000")},
    {"name": "Silver", "try_price": Decimal("250.00"), "coin_amount": 275, "trx_amount": Decimal("25.000000")},
    {"name": "Gold", "try_price": Decimal("500.00"), "coin_amount": 600, "trx_amount": Decimal("50.000000")},
]

DEFAULT_GAMES = [
    {"name": "PUBG Mobile", "requires_server": False, "id_label": "Game User ID"},
    {"name": "Free Fire", "requires_server": False, "id_label": "Player ID"},
]

DEFAULT_TEMPLATES = {
    "deposit_waiting": "Your deposit request has been received. Please wait for admin approval.",
    "order_received": "Your order is created. Our admin will complete delivery soon.",
}



def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

    with session_scope() as session:
        has_packages = session.scalar(select(CoinPackage.id).limit(1))
        if not has_packages:
            for pkg in DEFAULT_PACKAGES:
                session.add(CoinPackage(**pkg))

        has_games = session.scalar(select(Game.id).limit(1))
        if not has_games:
            for game in DEFAULT_GAMES:
                session.add(Game(**game))

        for key, value in DEFAULT_TEMPLATES.items():
            exists = session.scalar(select(MessageTemplate).where(MessageTemplate.key == key))
            if not exists:
                session.add(MessageTemplate(key=key, content=value))
