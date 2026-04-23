"""recurring rules

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27 13:20:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "INCOME",
                "EXPENSE",
                "TRANSFER",
                name="transaction_type",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "frequency",
            sa.Enum(
                "DAILY",
                "WEEKLY",
                "MONTHLY",
                "YEARLY",
                name="recurrence_frequency",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("interval", sa.Integer(), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("next_run_on", sa.Date(), nullable=False),
        sa.Column("last_run_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_recurring_rules_amount_positive")),
        sa.CheckConstraint(
            "interval >= 1 AND interval <= 365",
            name=op.f("ck_recurring_rules_interval_in_range"),
        ),
        sa.CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name=op.f("ck_recurring_rules_day_of_month_in_range"),
        ),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on",
            name=op.f("ck_recurring_rules_ends_after_start"),
        ),
        sa.CheckConstraint(
            "transaction_type <> 'TRANSFER'",
            name=op.f("ck_recurring_rules_not_a_transfer"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_recurring_rules_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_recurring_rules_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recurring_rules_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_rules")),
    )
    op.create_index("ix_recurring_rules_user_id", "recurring_rules", ["user_id"], unique=False)
    op.create_index(
        "ix_recurring_rules_account_id", "recurring_rules", ["account_id"], unique=False
    )
    op.create_index(
        "ix_recurring_rules_due",
        "recurring_rules",
        ["is_active", "next_run_on"],
        unique=False,
    )

    op.add_column("transactions", sa.Column("recurring_rule_id", sa.UUID(), nullable=True))
    op.add_column("transactions", sa.Column("occurrence_on", sa.Date(), nullable=True))
    op.create_foreign_key(
        op.f("fk_transactions_recurring_rule_id_recurring_rules"),
        "transactions",
        "recurring_rules",
        ["recurring_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_transactions_recurring_rule_id", "transactions", ["recurring_rule_id"], unique=False
    )
    op.create_index(
        "uq_transactions_recurring_occurrence",
        "transactions",
        ["recurring_rule_id", "occurrence_on"],
        unique=True,
        postgresql_where=sa.text("recurring_rule_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_recurring_occurrence", table_name="transactions")
    op.drop_index("ix_transactions_recurring_rule_id", table_name="transactions")
    op.drop_constraint(
        op.f("fk_transactions_recurring_rule_id_recurring_rules"),
        "transactions",
        type_="foreignkey",
    )
    op.drop_column("transactions", "occurrence_on")
    op.drop_column("transactions", "recurring_rule_id")
    op.drop_index("ix_recurring_rules_due", table_name="recurring_rules")
    op.drop_index("ix_recurring_rules_account_id", table_name="recurring_rules")
    op.drop_index("ix_recurring_rules_user_id", table_name="recurring_rules")
    op.drop_table("recurring_rules")
