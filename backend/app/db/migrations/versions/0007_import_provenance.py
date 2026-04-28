"""transaction import provenance

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27 13:40:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("import_hash", sa.String(length=64), nullable=True))
    op.add_column("transactions", sa.Column("import_batch_id", sa.UUID(), nullable=True))
    op.add_column("transactions", sa.Column("external_id", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_transactions_import_batch_id", "transactions", ["import_batch_id"], unique=False
    )
    op.create_index(
        "uq_transactions_user_import_hash",
        "transactions",
        ["user_id", "import_hash"],
        unique=True,
        postgresql_where=sa.text("import_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_user_import_hash", table_name="transactions")
    op.drop_index("ix_transactions_import_batch_id", table_name="transactions")
    op.drop_column("transactions", "external_id")
    op.drop_column("transactions", "import_batch_id")
    op.drop_column("transactions", "import_hash")
