"""add withdrawal requests

Revision ID: 20260219_0002
Revises: 20260218_0001
Create Date: 2026-02-19 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260219_0002"
down_revision = "20260218_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "withdrawal_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_coins", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("iban", sa.String(length=80), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("proof_file_id", sa.String(length=255), nullable=True),
        sa.Column("proof_file_type", sa.String(length=20), nullable=True),
        sa.Column("proof_received_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_withdrawal_requests_user_id", "withdrawal_requests", ["user_id"], unique=False)
    op.create_index("ix_withdrawal_requests_status", "withdrawal_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_withdrawal_requests_status", table_name="withdrawal_requests")
    op.drop_index("ix_withdrawal_requests_user_id", table_name="withdrawal_requests")
    op.drop_table("withdrawal_requests")
