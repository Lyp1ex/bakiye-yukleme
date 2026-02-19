"""add request status cards table

Revision ID: 20260219_0004
Revises: 20260219_0003
Create Date: 2026-02-19 05:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260219_0004"
down_revision = "20260219_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "request_status_cards" in inspector.get_table_names():
        return

    op.create_table(
        "request_status_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("flow_type", sa.String(length=20), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("request_code", sa.String(length=40), nullable=False),
        sa.Column("current_status", sa.String(length=40), nullable=False),
        sa.Column("timeline_text", sa.Text(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("last_sla_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.UniqueConstraint("flow_type", "request_id", name="uq_request_status_cards_flow_request"),
    )
    op.create_index("ix_request_status_cards_user_id", "request_status_cards", ["user_id"], unique=False)
    op.create_index(
        "ix_request_status_cards_user_telegram_id",
        "request_status_cards",
        ["user_telegram_id"],
        unique=False,
    )
    op.create_index("ix_request_status_cards_flow_type", "request_status_cards", ["flow_type"], unique=False)
    op.create_index("ix_request_status_cards_request_id", "request_status_cards", ["request_id"], unique=False)
    op.create_index(
        "ix_request_status_cards_request_code",
        "request_status_cards",
        ["request_code"],
        unique=False,
    )
    op.create_index(
        "ix_request_status_cards_current_status",
        "request_status_cards",
        ["current_status"],
        unique=False,
    )
    op.create_index("ix_request_status_cards_is_closed", "request_status_cards", ["is_closed"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "request_status_cards" not in inspector.get_table_names():
        return

    op.drop_index("ix_request_status_cards_is_closed", table_name="request_status_cards")
    op.drop_index("ix_request_status_cards_current_status", table_name="request_status_cards")
    op.drop_index("ix_request_status_cards_request_code", table_name="request_status_cards")
    op.drop_index("ix_request_status_cards_request_id", table_name="request_status_cards")
    op.drop_index("ix_request_status_cards_flow_type", table_name="request_status_cards")
    op.drop_index("ix_request_status_cards_user_telegram_id", table_name="request_status_cards")
    op.drop_index("ix_request_status_cards_user_id", table_name="request_status_cards")
    op.drop_table("request_status_cards")
