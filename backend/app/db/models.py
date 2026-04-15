"""ORM models.

Money is stored as `BigInteger` minor units alongside an explicit currency --
never `Float` (plan Section 9). Every user-owned table carries a `user_id` FK
so ownership can be enforced in queries and household support stays a feature
rather than a schema rewrite.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.accounts import AccountType
from app.domain.categories import CategoryKind
from app.domain.investments import Compounding, InvestmentType, RatePeriod
from app.domain.ledger import TransactionType


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SchemaMetadata(Base):
    """Records which application version last migrated this database."""

    __tablename__ = "schema_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    accounts: Mapped[list[Account]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    categories: Mapped[list[Category]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list[Budget]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    investments: Mapped[list[Investment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    investment_valuations: Mapped[list[InvestmentValuation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """A rotating refresh token, stored only as a hash (plan Section 10)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when this token is rotated, so a replayed token reveals the chain.
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    __table_args__ = (Index("ix_refresh_tokens_user_id_expires_at", "user_id", "expires_at"),)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type", native_enum=False, length=32), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    opening_balance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="accounts")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="account")
    investments: Mapped[list[Investment]] = relationship(back_populates="account")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_accounts_user_id_name"),
        Index("ix_accounts_user_id", "user_id"),
    )


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[CategoryKind] = mapped_column(
        SAEnum(CategoryKind, name="category_kind", native_enum=False, length=32), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="categories")
    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship(back_populates="parent")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="category")
    budgets: Mapped[list[Budget]] = relationship(back_populates="category")

    __table_args__ = (
        UniqueConstraint("user_id", "parent_id", "name", name="uq_categories_user_id_parent_id"),
        Index("ix_categories_user_id", "user_id"),
    )


class Budget(Base, TimestampMixin):
    """A monthly spending limit for one category.

    Periods are calendar months. `starts_on` is the first month the budget
    applies to and `ends_on`, when set, is the first month it no longer
    applies to (an exclusive boundary) -- storing a boundary rather than an
    inclusive end avoids the classic off-by-one "did December count?" bug.

    `amount_minor` is deliberately non-negative: a budget of zero is a valid
    "spend nothing here" statement, while a negative limit is nonsense.
    """

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    rollover_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="budgets")
    category: Mapped[Category] = relationship(back_populates="budgets")

    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="amount_non_negative"),
        CheckConstraint("EXTRACT(DAY FROM starts_on) = 1", name="starts_on_first_of_month"),
        CheckConstraint(
            "ends_on IS NULL OR EXTRACT(DAY FROM ends_on) = 1",
            name="ends_on_first_of_month",
        ),
        CheckConstraint("ends_on IS NULL OR ends_on > starts_on", name="ends_after_start"),
        # One *active* budget per category. Archived rows are excluded so a
        # category can be re-budgeted without deleting its history.
        Index(
            "uq_budgets_active_category",
            "user_id",
            "category_id",
            unique=True,
            postgresql_where=text("is_archived IS FALSE"),
        ),
        Index("ix_budgets_user_id", "user_id"),
        Index("ix_budgets_category_id", "category_id"),
    )


class Investment(Base, TimestampMixin):
    """A holding inside an investment account.

    A fixed-rate instrument carries a stated rate; a market-priced one is
    valued only through `InvestmentValuation` snapshots. The service enforces
    that those fields are consistent -- the database keeps the basic numeric
    invariants.
    """

    __tablename__ = "investments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    investment_type: Mapped[InvestmentType] = mapped_column(
        SAEnum(InvestmentType, name="investment_type", native_enum=False, length=32),
        nullable=False,
    )
    principal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    rate_period: Mapped[RatePeriod | None] = mapped_column(
        SAEnum(RatePeriod, name="rate_period", native_enum=False, length=16), nullable=True
    )
    compounding: Mapped[Compounding] = mapped_column(
        SAEnum(Compounding, name="compounding", native_enum=False, length=16),
        nullable=False,
        default=Compounding.SIMPLE,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="investments")
    account: Mapped[Account] = relationship(back_populates="investments")
    valuations: Mapped[list[InvestmentValuation]] = relationship(
        back_populates="investment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("principal_minor >= 0", name="principal_non_negative"),
        CheckConstraint("rate IS NULL OR rate > 0", name="rate_positive_when_set"),
        CheckConstraint(
            "maturity_date IS NULL OR maturity_date >= start_date", name="maturity_after_start"
        ),
        UniqueConstraint("user_id", "name", name="uq_investments_user_id_name"),
        Index("ix_investments_user_id", "user_id"),
        Index("ix_investments_account_id", "account_id"),
    )


class InvestmentValuation(Base):
    """A recorded value for a holding at a date.

    Snapshots make returns chartable for instruments without a price feed. A
    corrected value is a new observation, not a rewrite of history.
    """

    __tablename__ = "investment_valuations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("investments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    investment: Mapped[Investment] = relationship(back_populates="valuations")
    user: Mapped[User] = relationship(back_populates="investment_valuations")

    __table_args__ = (
        CheckConstraint("value_minor >= 0", name="value_non_negative"),
        CheckConstraint("length(source) > 0", name="source_not_empty"),
        UniqueConstraint(
            "investment_id", "as_of", name="uq_investment_valuations_investment_id_as_of"
        ),
        Index("ix_investment_valuations_user_id_as_of", "user_id", "as_of"),
    )


class Transaction(Base, TimestampMixin):
    """A single ledger entry.

    `amount_minor` is a positive magnitude; direction comes from
    `transaction_type`. A transfer is stored as two rows sharing a
    `transfer_group_id`, which together net to zero.
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type", native_enum=False, length=32),
        nullable=False,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Direction applied: positive credits the account, negative debits it.
    # Derived from transaction_type on write (and from the transfer leg), then
    # stored so balance queries are a plain SUM with no CASE over enum values.
    signed_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="transactions")
    account: Mapped[Account] = relationship(back_populates="transactions")
    category: Mapped[Category | None] = relationship(back_populates="transactions")

    __table_args__ = (
        # Enforced in the database, not just the application: a zero or
        # negative magnitude is never valid regardless of how it got here.
        CheckConstraint("amount_minor > 0", name="amount_minor_positive"),
        CheckConstraint(
            "abs(signed_amount_minor) = amount_minor", name="signed_amount_matches_magnitude"
        ),
        Index("ix_transactions_user_id_occurred_on", "user_id", "occurred_on"),
        Index("ix_transactions_account_id", "account_id"),
        Index("ix_transactions_category_id", "category_id"),
        Index("ix_transactions_transfer_group_id", "transfer_group_id"),
    )


class ExchangeRate(Base):
    """An append-only observation of one currency pair at a point in time.

    `rate` means one unit of `base_currency` buys `rate` units of
    `quote_currency`. Rows are never updated: a corrected rate is a new row
    with a later `as_of`, so historical reports remain reproducible.

    Rows with a `user_id` are private, user-entered rates; rows with a NULL
    `user_id` are fetched from the configured provider and shared. Resolution
    prefers the user's own rate, then the shared one (see `app.services.fx`).
    """

    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("rate > 0", name="rate_positive"),
        CheckConstraint("base_currency <> quote_currency", name="currencies_differ"),
        # The API never records a rate without provenance.
        CheckConstraint("length(source) > 0", name="source_not_empty"),
        Index("ix_exchange_rates_pair_as_of", "base_currency", "quote_currency", "as_of"),
        Index("ix_exchange_rates_user_id", "user_id"),
        # Partial uniques make concurrent duplicate writes fail in the database.
        # Postgres treats NULLs as distinct, hence one index per owner shape.
        Index(
            "uq_exchange_rates_global_observation",
            "base_currency",
            "quote_currency",
            "as_of",
            "source",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
        Index(
            "uq_exchange_rates_user_observation",
            "user_id",
            "base_currency",
            "quote_currency",
            "as_of",
            "source",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )


class AuditLog(Base):
    """Append-only record of financial mutations (plan Section 10)."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_logs_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
    )
