"""initial schema

Revision ID: 20260218_0001
Revises:
Create Date: 2026-02-18 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260218_0001"
down_revision = None
branch_labels = None
depends_on = None



def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("coin_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "coin_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("try_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("coin_amount", sa.Integer(), nullable=False),
        sa.Column("trx_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("requires_server", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id_label", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("name", name="uq_games_name"),
    )

    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("key", name="uq_message_templates_key"),
    )
    op.create_index(
        "ix_message_templates_key",
        "message_templates",
        ["key"],
        unique=True,
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_coins", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
    )
    op.create_index("ix_products_game_id", "products", ["game_id"], unique=False)

    op.create_table(
        "deposit_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("receipt_file_id", sa.String(length=255), nullable=False),
        sa.Column("receipt_file_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["package_id"], ["coin_packages.id"]),
    )
    op.create_index("ix_deposit_requests_user_id", "deposit_requests", ["user_id"], unique=False)
    op.create_index("ix_deposit_requests_status", "deposit_requests", ["status"], unique=False)

    op.create_table(
        "crypto_deposit_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=False),
        sa.Column("expected_trx", sa.Numeric(18, 6), nullable=False),
        sa.Column("wallet_address", sa.String(length=128), nullable=False),
        sa.Column("tx_hash", sa.String(length=128), nullable=True),
        sa.Column("tx_from_address", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["package_id"], ["coin_packages.id"]),
        sa.UniqueConstraint("tx_hash", name="uq_crypto_deposit_requests_tx_hash"),
    )
    op.create_index(
        "ix_crypto_deposit_requests_user_id",
        "crypto_deposit_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_crypto_deposit_requests_status",
        "crypto_deposit_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("game_user_id", sa.String(length=120), nullable=True),
        sa.Column("iban", sa.String(length=80), nullable=True),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("completed_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_index("ix_orders_product_id", "orders", ["product_id"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)

    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_admin_logs_admin_telegram_id", "admin_logs", ["admin_telegram_id"], unique=False)



def downgrade() -> None:
    op.drop_index("ix_admin_logs_admin_telegram_id", table_name="admin_logs")
    op.drop_table("admin_logs")

    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_product_id", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_crypto_deposit_requests_status", table_name="crypto_deposit_requests")
    op.drop_index("ix_crypto_deposit_requests_user_id", table_name="crypto_deposit_requests")
    op.drop_table("crypto_deposit_requests")

    op.drop_index("ix_deposit_requests_status", table_name="deposit_requests")
    op.drop_index("ix_deposit_requests_user_id", table_name="deposit_requests")
    op.drop_table("deposit_requests")

    op.drop_index("ix_products_game_id", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_message_templates_key", table_name="message_templates")
    op.drop_table("message_templates")

    op.drop_table("games")
    op.drop_table("coin_packages")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
