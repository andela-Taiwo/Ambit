"""budgets

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27 12:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("rollover_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_minor >= 0", name=op.f("ck_budgets_amount_non_negative")),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM starts_on) = 1",
            name=op.f("ck_budgets_starts_on_first_of_month"),
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR EXTRACT(DAY FROM ends_on) = 1",
            name=op.f("ck_budgets_ends_on_first_of_month"),
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on > starts_on",
            name=op.f("ck_budgets_ends_after_start"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_budgets_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_budgets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budgets")),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"], unique=False)
    op.create_index("ix_budgets_category_id", "budgets", ["category_id"], unique=False)
    op.create_index(
        "uq_budgets_active_category",
        "budgets",
        ["user_id", "category_id"],
        unique=True,
        postgresql_where=sa.text("is_archived IS FALSE"),
    )


def downgrade() -> None:
    op.drop_index("uq_budgets_active_category", table_name="budgets")
    op.drop_index("ix_budgets_category_id", table_name="budgets")
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")
