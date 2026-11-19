"""CSV statement import with atomic validation and de-duplication.

Validation happens for the whole file before anything is written. A malformed
row rejects the import with row-numbered errors, because a half-applied bank
statement is materially worse than asking the user to fix the file.

Duplicate detection uses a stable per-user hash. When the source provides a
bank reference that alone identifies the row; otherwise an occurrence ordinal
is included so identical rows within one file are preserved while re-importing
the same file is a no-op.
"""

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ImportValidationError, ValidationError
from app.db.models import Category, Transaction, User
from app.domain.categories import CategoryKind
from app.domain.imports import (
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_LENGTH,
    MAX_IMPORT_ROWS,
    ImportParseError,
    classify,
    parse_amount,
)
from app.domain.ledger import TransactionType, signed_amount
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.schemas.imports import (
    CsvImportRequest,
    CsvImportResult,
    CsvImportRowError,
)
from app.services import audit
from app.services.accounts import get_account
from app.services.categories import get_category

MAX_REPORTED_ERRORS = 100


@dataclass(frozen=True, slots=True)
class _PreparedRow:
    row_number: int
    occurred_on: date
    amount_minor: int
    transaction_type: TransactionType
    category_id: uuid.UUID | None
    description: str
    external_id: str | None
    import_hash: str


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_date(value: str, *, date_format: str) -> date:
    text = value.strip()
    if not text:
        raise ImportParseError("Date is empty")
    try:
        return datetime.strptime(text, date_format).date()
    except ValueError as exc:
        raise ImportParseError(f"Date {value!r} does not match {date_format!r}") from exc


def _category_lookup(categories: list[Category]) -> dict[str, list[Category]]:
    lookup: dict[str, list[Category]] = {}
    for category in categories:
        lookup.setdefault(category.name.casefold(), []).append(category)
    return lookup


def _resolve_category(
    *,
    raw_name: str | None,
    default_category: Category | None,
    transaction_type: TransactionType,
    lookup: dict[str, list[Category]],
) -> uuid.UUID | None:
    expected = (
        CategoryKind.INCOME if transaction_type is TransactionType.INCOME else CategoryKind.EXPENSE
    )

    if raw_name is not None and raw_name.strip():
        matches = lookup.get(raw_name.strip().casefold(), [])
        if not matches:
            raise ImportParseError(f"Unknown category {raw_name!r}")
        if len(matches) > 1:
            raise ImportParseError(f"Category {raw_name!r} is ambiguous")
        category = matches[0]
        if category.is_archived:
            raise ImportParseError(f"Category {category.name!r} is archived")
        if category.kind is not expected:
            raise ImportParseError(
                f"Category {category.name!r} does not match a {transaction_type.value} row"
            )
        return category.id

    if default_category is None:
        return None
    if default_category.kind is not expected:
        raise ImportParseError(
            f"Default category {default_category.name!r} does not match a "
            f"{transaction_type.value} row"
        )
    return default_category.id


async def _load_categories(session: AsyncSession, user_id: uuid.UUID) -> list[Category]:
    return list(
        await session.scalars(
            select(Category).where(Category.user_id == user_id).order_by(Category.name)
        )
    )


async def _existing_hashes(
    session: AsyncSession, user_id: uuid.UUID, hashes: list[str]
) -> set[str]:
    found: set[str] = set()
    for start in range(0, len(hashes), 1000):
        chunk = hashes[start : start + 1000]
        found.update(
            list(
                await session.scalars(
                    select(Transaction.import_hash).where(
                        Transaction.user_id == user_id,
                        Transaction.import_hash.in_(chunk),
                    )
                )
            )
        )
    return found


async def import_csv(
    session: AsyncSession, user: User, payload: CsvImportRequest
) -> CsvImportResult:
    account = await get_account(session, user.id, payload.account_id)
    if account.is_archived:
        raise ValidationError("Cannot import into an archived account")

    currency = Currency(payload.currency or account.currency)
    if currency.code != account.currency:
        raise ValidationError(
            f"Import currency {currency.code} does not match account currency {account.currency}"
        )

    default_category: Category | None = None
    if payload.default_category_id is not None:
        default_category = await get_category(session, user.id, payload.default_category_id)
        if default_category.is_archived:
            raise ValidationError("Cannot import into an archived category")

    categories = await _load_categories(session, user.id)
    lookup = _category_lookup(categories)

    reader = csv.DictReader(io.StringIO(payload.csv.lstrip("\ufeff")))
    fieldnames = reader.fieldnames or []
    required = {payload.mapping.date, payload.mapping.amount}
    optional = {
        column
        for column in (
            payload.mapping.description,
            payload.mapping.category,
            payload.mapping.type,
            payload.mapping.external_id,
        )
        if column
    }
    missing = (required | optional) - set(fieldnames)
    if missing:
        raise ImportValidationError(
            f"CSV is missing mapped column(s): {', '.join(sorted(missing))}",
            details={"error_count": 1, "errors": [{"row": 1, "message": "Missing column(s)"}]},
        )

    prepared: list[_PreparedRow] = []
    errors: list[CsvImportRowError] = []
    error_count = 0
    occurrence_counts: dict[str, int] = {}
    seen_hashes: set[str] = set()
    duplicate_rows = 0
    total_rows = 0

    def fail(row_number: int, message: str) -> None:
        nonlocal error_count
        error_count += 1
        if len(errors) < MAX_REPORTED_ERRORS:
            errors.append(CsvImportRowError(row=row_number, message=message))

    for row_number, row in enumerate(reader, start=2):
        if all(not (value or "").strip() for value in row.values()):
            continue
        total_rows += 1
        if total_rows > MAX_IMPORT_ROWS:
            fail(row_number, f"Import is limited to {MAX_IMPORT_ROWS} rows")
            break

        try:
            occurred_on = _parse_date(
                row.get(payload.mapping.date) or "", date_format=payload.date_format
            )
            amount = parse_amount(row.get(payload.mapping.amount) or "")
            type_value = row.get(payload.mapping.type) if payload.mapping.type is not None else None
            transaction_type = classify(
                amount, type_value=type_value, convention=payload.amount_sign
            )
            amount_minor = to_minor_units(abs(amount), currency)
            category_id = _resolve_category(
                raw_name=(
                    row.get(payload.mapping.category)
                    if payload.mapping.category is not None
                    else None
                ),
                default_category=default_category,
                transaction_type=transaction_type,
                lookup=lookup,
            )

            raw_description = (
                row.get(payload.mapping.description)
                if payload.mapping.description is not None
                else None
            )
            description = (raw_description or "").strip() or payload.default_description
            if len(description) > MAX_DESCRIPTION_LENGTH:
                raise ImportParseError(f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters")

            raw_external_id = (
                row.get(payload.mapping.external_id)
                if payload.mapping.external_id is not None
                else None
            )
            external_id = (raw_external_id or "").strip() or None
            if external_id is not None and len(external_id) > MAX_EXTERNAL_ID_LENGTH:
                raise ImportParseError(f"External id exceeds {MAX_EXTERNAL_ID_LENGTH} characters")

            signed_minor = signed_amount(amount_minor, transaction_type)
            if external_id is not None:
                import_hash = _sha256(f"external|{account.id}|{external_id}")
            else:
                base = (
                    f"row|{account.id}|{occurred_on.isoformat()}|{signed_minor}|"
                    f"{currency.code}|{description.casefold()}|{category_id}|"
                    f"{transaction_type.value}"
                )
                ordinal = occurrence_counts.get(base, 0)
                occurrence_counts[base] = ordinal + 1
                import_hash = _sha256(f"{base}|{ordinal}")

            if import_hash in seen_hashes:
                duplicate_rows += 1
                continue
            seen_hashes.add(import_hash)
            prepared.append(
                _PreparedRow(
                    row_number=row_number,
                    occurred_on=occurred_on,
                    amount_minor=amount_minor,
                    transaction_type=transaction_type,
                    category_id=category_id,
                    description=description,
                    external_id=external_id,
                    import_hash=import_hash,
                )
            )
        except (ImportParseError, InvalidAmountError) as exc:
            fail(row_number, str(exc))

    if error_count:
        raise ImportValidationError(
            f"{error_count} row(s) failed validation; nothing was imported",
            details={
                "error_count": error_count,
                "errors": [error.model_dump() for error in errors],
            },
        )

    if total_rows == 0:
        raise ImportValidationError(
            "CSV contains no data rows",
            details={"error_count": 0, "errors": []},
        )

    existing = await _existing_hashes(session, user.id, [row.import_hash for row in prepared])
    fresh = [row for row in prepared if row.import_hash not in existing]
    skipped = duplicate_rows + len(prepared) - len(fresh)

    if payload.dry_run:
        return CsvImportResult(
            imported_count=len(fresh),
            skipped_count=skipped,
            error_count=0,
            errors=[],
            batch_id=None,
            dry_run=True,
        )

    if not fresh:
        return CsvImportResult(
            imported_count=0,
            skipped_count=skipped,
            error_count=0,
            errors=[],
            batch_id=None,
            dry_run=False,
        )

    batch_id = uuid.uuid4()
    session.add_all(
        [
            Transaction(
                user_id=user.id,
                account_id=account.id,
                category_id=row.category_id,
                transaction_type=row.transaction_type,
                amount_minor=row.amount_minor,
                signed_amount_minor=signed_amount(row.amount_minor, row.transaction_type),
                currency=currency.code,
                occurred_on=row.occurred_on,
                description=row.description,
                import_hash=row.import_hash,
                import_batch_id=batch_id,
                external_id=row.external_id,
            )
            for row in fresh
        ]
    )
    audit.record(
        session,
        user_id=user.id,
        entity_type="import_batch",
        entity_id=batch_id,
        action="imported",
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Import conflicted with a concurrent import; please retry") from exc

    return CsvImportResult(
        imported_count=len(fresh),
        skipped_count=skipped,
        error_count=0,
        errors=[],
        batch_id=batch_id,
        dry_run=False,
    )


__all__ = ["import_csv"]
