"""exchange rates

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27 12:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rate > 0", name=op.f("ck_exchange_rates_rate_positive")),
        sa.CheckConstraint(
            "base_currency <> quote_currency",
            name=op.f("ck_exchange_rates_currencies_differ"),
        ),
        sa.CheckConstraint("length(source) > 0", name=op.f("ck_exchange_rates_source_not_empty")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_exchange_rates_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exchange_rates")),
    )
    op.create_index(
        "ix_exchange_rates_pair_as_of",
        "exchange_rates",
        ["base_currency", "quote_currency", "as_of"],
        unique=False,
    )
    op.create_index("ix_exchange_rates_user_id", "exchange_rates", ["user_id"], unique=False)
    op.create_index(
        "uq_exchange_rates_global_observation",
        "exchange_rates",
        ["base_currency", "quote_currency", "as_of", "source"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_index(
        "uq_exchange_rates_user_observation",
        "exchange_rates",
        ["user_id", "base_currency", "quote_currency", "as_of", "source"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_exchange_rates_user_observation", table_name="exchange_rates")
    op.drop_index("uq_exchange_rates_global_observation", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_user_id", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_pair_as_of", table_name="exchange_rates")
    op.drop_table("exchange_rates")
