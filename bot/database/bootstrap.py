from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from bot.database.base import Base
from bot.database.session import engine, session_scope
from bot.models import CoinPackage, MessageTemplate
from bot.texts.messages import DEFAULT_TEXT_TEMPLATES, LEGACY_TEXT_TEMPLATES_EN


DEFAULT_PACKAGES = [
    {"name": "Başlangıç Paketi", "try_price": Decimal("100.00"), "coin_amount": 100, "trx_amount": Decimal("10.000000")},
    {"name": "Orta Paket", "try_price": Decimal("250.00"), "coin_amount": 275, "trx_amount": Decimal("25.000000")},
    {"name": "Büyük Paket", "try_price": Decimal("500.00"), "coin_amount": 600, "trx_amount": Decimal("50.000000")},
]



def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

    with session_scope() as session:
        has_packages = session.scalar(select(CoinPackage.id).limit(1))
        if not has_packages:
            for pkg in DEFAULT_PACKAGES:
                session.add(CoinPackage(**pkg))

        for key, value in DEFAULT_TEXT_TEMPLATES.items():
            exists = session.scalar(select(MessageTemplate).where(MessageTemplate.key == key))
            if not exists:
                session.add(MessageTemplate(key=key, content=value))
                continue

            legacy_content = LEGACY_TEXT_TEMPLATES_EN.get(key)
            if legacy_content and (exists.content or "").strip() == legacy_content.strip():
                # Kullanıcı metni elle değiştirmediyse, eski İngilizce varsayılanı Türkçeye çevir.
                exists.content = value
