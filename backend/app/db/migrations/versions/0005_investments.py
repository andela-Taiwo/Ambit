"""investments and valuation snapshots

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27 13:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "investment_type",
            sa.Enum(
                "FIXED_RATE",
                "MARKET_PRICED",
                name="investment_type",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("principal_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column(
            "rate_period",
            sa.Enum(
                "ANNUAL",
                "MONTHLY",
                name="rate_period",
                native_enum=False,
                length=16,
            ),
            nullable=True,
        ),
        sa.Column(
            "compounding",
            sa.Enum(
                "SIMPLE",
                "MONTHLY",
                name="compounding",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "principal_minor >= 0", name=op.f("ck_investments_principal_non_negative")
        ),
        sa.CheckConstraint(
            "rate IS NULL OR rate > 0", name=op.f("ck_investments_rate_positive_when_set")
        ),
        sa.CheckConstraint(
            "maturity_date IS NULL OR maturity_date >= start_date",
            name=op.f("ck_investments_maturity_after_start"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_investments_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_investments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investments")),
        sa.UniqueConstraint("user_id", "name", name="uq_investments_user_id_name"),
    )
    op.create_index("ix_investments_user_id", "investments", ["user_id"], unique=False)
    op.create_index("ix_investments_account_id", "investments", ["account_id"], unique=False)

    op.create_table(
        "investment_valuations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("investment_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("value_minor", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "value_minor >= 0", name=op.f("ck_investment_valuations_value_non_negative")
        ),
        sa.CheckConstraint(
            "length(source) > 0", name=op.f("ck_investment_valuations_source_not_empty")
        ),
        sa.ForeignKeyConstraint(
            ["investment_id"],
            ["investments.id"],
            name=op.f("fk_investment_valuations_investment_id_investments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_investment_valuations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_valuations")),
        sa.UniqueConstraint(
            "investment_id",
            "as_of",
            name="uq_investment_valuations_investment_id_as_of",
        ),
    )
    op.create_index(
        "ix_investment_valuations_user_id_as_of",
        "investment_valuations",
        ["user_id", "as_of"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_investment_valuations_user_id_as_of", table_name="investment_valuations")
    op.drop_table("investment_valuations")
    op.drop_index("ix_investments_account_id", table_name="investments")
    op.drop_index("ix_investments_user_id", table_name="investments")
    op.drop_table("investments")
