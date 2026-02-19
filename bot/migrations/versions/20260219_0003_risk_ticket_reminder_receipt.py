"""add risk flags, support tickets, reminder events and receipt fingerprints

Revision ID: 20260219_0003
Revises: 20260219_0002
Create Date: 2026-02-19 00:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260219_0003"
down_revision = "20260219_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipt_fingerprints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("first_deposit_request_id", sa.Integer(), nullable=True),
        sa.Column("last_deposit_request_id", sa.Integer(), nullable=True),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["first_deposit_request_id"], ["deposit_requests.id"]),
        sa.ForeignKeyConstraint(["last_deposit_request_id"], ["deposit_requests.id"]),
        sa.UniqueConstraint("file_sha256", name="uq_receipt_fingerprints_sha256"),
    )
    op.create_index(
        "ix_receipt_fingerprints_file_sha256",
        "receipt_fingerprints",
        ["file_sha256"],
        unique=True,
    )
    op.create_index("ix_receipt_fingerprints_user_id", "receipt_fingerprints", ["user_id"], unique=False)

    op.create_table(
        "risk_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_risk_flags_user_id", "risk_flags", ["user_id"], unique=False)
    op.create_index("ix_risk_flags_source", "risk_flags", ["source"], unique=False)
    op.create_index("ix_risk_flags_is_resolved", "risk_flags", ["is_resolved"], unique=False)

    op.create_table(
        "reminder_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
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
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_reminder_events_entity"),
    )
    op.create_index("ix_reminder_events_entity_type", "reminder_events", ["entity_type"], unique=False)
    op.create_index("ix_reminder_events_entity_id", "reminder_events", ["entity_id"], unique=False)

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_request_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"], unique=False)
    op.create_index("ix_support_tickets_source_type", "support_tickets", ["source_type"], unique=False)
    op.create_index(
        "ix_support_tickets_source_request_id",
        "support_tickets",
        ["source_request_id"],
        unique=False,
    )
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_source_request_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_source_type", table_name="support_tickets")
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_table("support_tickets")

    op.drop_index("ix_reminder_events_entity_id", table_name="reminder_events")
    op.drop_index("ix_reminder_events_entity_type", table_name="reminder_events")
    op.drop_table("reminder_events")

    op.drop_index("ix_risk_flags_is_resolved", table_name="risk_flags")
    op.drop_index("ix_risk_flags_source", table_name="risk_flags")
    op.drop_index("ix_risk_flags_user_id", table_name="risk_flags")
    op.drop_table("risk_flags")

    op.drop_index("ix_receipt_fingerprints_user_id", table_name="receipt_fingerprints")
    op.drop_index("ix_receipt_fingerprints_file_sha256", table_name="receipt_fingerprints")
    op.drop_table("receipt_fingerprints")

