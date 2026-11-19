"""Recurring-rule CRUD and due-occurrence materialisation."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.models import RecurringRule, Transaction
from app.domain.categories import CategoryKind
from app.domain.ledger import TransactionType, signed_amount
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.domain.recurring import (
    RecurrenceError,
    RecurrenceFrequency,
    advance,
    due_occurrences,
    validate_schedule,
)
from app.schemas.recurring import RecurringRuleCreate, RecurringRuleUpdate, RecurringRunResponse
from app.services import audit
from app.services.accounts import get_account
from app.services.categories import get_category


def _owned(user_id: uuid.UUID) -> Select[tuple[RecurringRule]]:
    return select(RecurringRule).where(RecurringRule.user_id == user_id)


async def get_rule(session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID) -> RecurringRule:
    rule = await session.scalar(_owned(user_id).where(RecurringRule.id == rule_id))
    if rule is None:
        raise NotFoundError("Recurring rule not found")
    return rule


async def list_rules(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    account_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> tuple[list[RecurringRule], int]:
    query = _owned(user_id)
    if account_id is not None:
        query = query.where(RecurringRule.account_id == account_id)
    if not include_inactive:
        query = query.where(RecurringRule.is_active.is_(True))

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(RecurringRule.next_run_on, RecurringRule.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def _assert_category_matches(
    session: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID | None,
    transaction_type: TransactionType,
) -> None:
    if category_id is None:
        return
    category = await get_category(session, user_id, category_id)
    expected = (
        CategoryKind.INCOME if transaction_type is TransactionType.INCOME else CategoryKind.EXPENSE
    )
    if category.kind is not expected:
        raise ValidationError(
            f"Category kind {category.kind} does not match a {transaction_type} rule"
        )


async def create_rule(
    session: AsyncSession, user_id: uuid.UUID, payload: RecurringRuleCreate
) -> RecurringRule:
    account = await get_account(session, user_id, payload.account_id)
    if payload.currency != account.currency:
        raise ValidationError(
            f"Rule currency {payload.currency} does not match account currency {account.currency}"
        )

    transaction_type = TransactionType(payload.transaction_type)
    await _assert_category_matches(session, user_id, payload.category_id, transaction_type)

    day_of_month = payload.day_of_month
    if payload.frequency in (RecurrenceFrequency.MONTHLY, RecurrenceFrequency.YEARLY):
        day_of_month = day_of_month or payload.starts_on.day

    try:
        validate_schedule(
            frequency=payload.frequency,
            interval=payload.interval,
            day_of_month=day_of_month,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
        )
    except RecurrenceError as exc:
        raise ValidationError(str(exc)) from exc

    currency = Currency(payload.currency)
    try:
        amount_minor = to_minor_units(payload.amount, currency)
    except InvalidAmountError as exc:
        raise ValidationError(str(exc)) from exc

    rule = RecurringRule(
        user_id=user_id,
        account_id=account.id,
        category_id=payload.category_id,
        description=payload.description,
        transaction_type=transaction_type,
        amount_minor=amount_minor,
        currency=currency.code,
        frequency=payload.frequency,
        interval=payload.interval,
        day_of_month=day_of_month,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        next_run_on=payload.starts_on,
        is_active=True,
    )
    session.add(rule)
    await session.flush()
    audit.record(
        session,
        user_id=user_id,
        entity_type="recurring_rule",
        entity_id=rule.id,
        action="created",
    )
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_rule(
    session: AsyncSession,
    user_id: uuid.UUID,
    rule_id: uuid.UUID,
    payload: RecurringRuleUpdate,
) -> RecurringRule:
    rule = await get_rule(session, user_id, rule_id)

    if "category_id" in payload.model_fields_set:
        await _assert_category_matches(session, user_id, payload.category_id, rule.transaction_type)
        rule.category_id = payload.category_id

    if payload.description is not None:
        rule.description = payload.description

    if payload.amount is not None:
        try:
            rule.amount_minor = to_minor_units(payload.amount, Currency(rule.currency))
        except InvalidAmountError as exc:
            raise ValidationError(str(exc)) from exc

    if "ends_on" in payload.model_fields_set:
        if payload.ends_on is not None and payload.ends_on < rule.starts_on:
            raise ValidationError("ends_on cannot be before starts_on")
        rule.ends_on = payload.ends_on

    if payload.is_active is not None:
        rule.is_active = payload.is_active

    audit.record(
        session,
        user_id=user_id,
        entity_type="recurring_rule",
        entity_id=rule.id,
        action="updated",
    )
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_rule(session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    rule = await get_rule(session, user_id, rule_id)
    await session.delete(rule)
    audit.record(
        session,
        user_id=user_id,
        entity_type="recurring_rule",
        entity_id=rule.id,
        action="deleted",
    )
    await session.commit()


async def generate_due(
    session: AsyncSession, rule: RecurringRule, *, as_of: date
) -> RecurringRunResponse:
    """Materialise every due occurrence for one rule, idempotently.

    Rows already present for an occurrence are counted as skipped and the
    cursor still advances past them; a retry therefore converges rather than
    looping forever on a duplicate.
    """
    occurrences = due_occurrences(
        next_run_on=rule.next_run_on,
        frequency=rule.frequency,
        interval=rule.interval,
        day_of_month=rule.day_of_month,
        anchor_month=rule.starts_on.month if rule.frequency is RecurrenceFrequency.YEARLY else None,
        as_of=as_of,
        ends_on=rule.ends_on,
    )

    if not occurrences:
        return RecurringRunResponse(
            rule_id=rule.id,
            generated_count=0,
            skipped_count=0,
            last_occurrence_on=None,
            next_run_on=rule.next_run_on,
        )

    existing = set(
        await session.scalars(
            select(Transaction.occurrence_on).where(
                Transaction.recurring_rule_id == rule.id,
                Transaction.occurrence_on.in_(occurrences),
            )
        )
    )

    generated = 0
    skipped = 0
    last_generated: date | None = None
    for occurrence in occurrences:
        if occurrence in existing:
            skipped += 1
            continue
        session.add(
            Transaction(
                user_id=rule.user_id,
                account_id=rule.account_id,
                category_id=rule.category_id,
                transaction_type=rule.transaction_type,
                amount_minor=rule.amount_minor,
                signed_amount_minor=signed_amount(rule.amount_minor, rule.transaction_type),
                currency=rule.currency,
                occurred_on=occurrence,
                description=rule.description,
                recurring_rule_id=rule.id,
                occurrence_on=occurrence,
            )
        )
        generated += 1
        last_generated = occurrence

    rule.next_run_on = advance(
        occurrences[-1],
        frequency=rule.frequency,
        interval=rule.interval,
        day_of_month=rule.day_of_month,
        anchor_month=rule.starts_on.month if rule.frequency is RecurrenceFrequency.YEARLY else None,
    )
    rule.last_run_on = occurrences[-1]
    if generated:
        audit.record(
            session,
            user_id=rule.user_id,
            entity_type="recurring_rule",
            entity_id=rule.id,
            action="generated",
        )
    await session.commit()
    await session.refresh(rule)

    return RecurringRunResponse(
        rule_id=rule.id,
        generated_count=generated,
        skipped_count=skipped,
        last_occurrence_on=last_generated,
        next_run_on=rule.next_run_on,
    )


async def run_rule(
    session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID, *, as_of: date | None = None
) -> RecurringRunResponse:
    rule = await session.scalar(
        _owned(user_id).where(RecurringRule.id == rule_id).with_for_update()
    )
    if rule is None:
        raise NotFoundError("Recurring rule not found")
    if not rule.is_active:
        raise ValidationError("Cannot run an inactive recurring rule")
    return await generate_due(session, rule, as_of=as_of or datetime.now(UTC).date())


async def run_all_due(session: AsyncSession, *, as_of: date) -> list[RecurringRunResponse]:
    """Materialise every active rule due by `as_of`, skipping locked rules."""
    rules = list(
        await session.scalars(
            select(RecurringRule)
            .where(
                RecurringRule.is_active.is_(True),
                RecurringRule.next_run_on <= as_of,
                or_(
                    RecurringRule.ends_on.is_(None),
                    RecurringRule.next_run_on <= RecurringRule.ends_on,
                ),
            )
            .order_by(RecurringRule.next_run_on)
            .with_for_update(skip_locked=True)
        )
    )
    return [await generate_due(session, rule, as_of=as_of) for rule in rules]
