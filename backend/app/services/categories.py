"""Category service."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Category
from app.domain.categories import (
    CategoryError,
    CategoryKind,
    validate_parent_assignment,
)
from app.schemas.categories import CategoryCreate, CategoryUpdate


def _owned(user_id: uuid.UUID) -> Select[tuple[Category]]:
    return select(Category).where(Category.user_id == user_id)


async def get_category(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> Category:
    category = await session.scalar(_owned(user_id).where(Category.id == category_id))
    if category is None:
        raise NotFoundError("Category not found")
    return category


async def _ancestor_ids(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> list[uuid.UUID]:
    """Walk from a category up to its root, returning the chain it belongs to.

    Bounded by the domain's depth limit, so this cannot loop indefinitely even
    if bad data somehow created a cycle.
    """
    chain: list[uuid.UUID] = []
    current: uuid.UUID | None = category_id

    while current is not None and len(chain) < 16:
        node = await session.scalar(_owned(user_id).where(Category.id == current))
        if node is None:
            break
        chain.append(node.id)
        current = node.parent_id

    return chain


async def list_categories(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    kind: CategoryKind | None = None,
    include_archived: bool = False,
) -> tuple[list[Category], int]:
    query = _owned(user_id)
    if kind is not None:
        query = query.where(Category.kind == kind)
    if not include_archived:
        query = query.where(Category.is_archived.is_(False))

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(query.order_by(Category.name).limit(limit).offset(offset))
    return list(rows), int(total or 0)


async def _assert_name_is_free(
    session: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    query = _owned(user_id).where(Category.name == name)
    query = (
        query.where(Category.parent_id.is_(None))
        if parent_id is None
        else query.where(Category.parent_id == parent_id)
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)

    if await session.scalar(query) is not None:
        raise ConflictError("A category with that name already exists here")


async def create_category(
    session: AsyncSession, user_id: uuid.UUID, payload: CategoryCreate
) -> Category:
    if payload.parent_id is not None:
        parent = await get_category(session, user_id, payload.parent_id)
        ancestors = await _ancestor_ids(session, user_id, parent.id)
        try:
            validate_parent_assignment(
                category_id=uuid.uuid4(), parent_id=parent.id, ancestor_ids=ancestors
            )
        except CategoryError as exc:
            raise ValidationError(str(exc)) from exc

    await _assert_name_is_free(session, user_id, payload.name, payload.parent_id)

    category = Category(
        user_id=user_id,
        name=payload.name,
        kind=payload.kind,
        parent_id=payload.parent_id,
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update_category(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID, payload: CategoryUpdate
) -> Category:
    category = await get_category(session, user_id, category_id)

    if payload.parent_id is not None:
        parent = await get_category(session, user_id, payload.parent_id)
        ancestors = await _ancestor_ids(session, user_id, parent.id)
        try:
            validate_parent_assignment(
                category_id=category.id, parent_id=parent.id, ancestor_ids=ancestors
            )
        except CategoryError as exc:
            raise ValidationError(str(exc)) from exc
        category.parent_id = parent.id

    if payload.name is not None and payload.name != category.name:
        await _assert_name_is_free(
            session, user_id, payload.name, category.parent_id, exclude_id=category.id
        )
        category.name = payload.name

    if payload.is_archived is not None:
        category.is_archived = payload.is_archived

    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    """Delete a category. Transactions survive with `category_id` set to NULL."""
    category = await get_category(session, user_id, category_id)
    await session.delete(category)
    await session.commit()


async def category_subtree_map(
    session: AsyncSession, user_id: uuid.UUID
) -> dict[uuid.UUID, frozenset[uuid.UUID]]:
    """Map every category to itself plus all of its descendants.

    Budget and report roll-ups need this repeatedly. Loading the (small,
    user-owned) category tree once and walking it in memory avoids a recursive
    CTE per budget while staying cycle-safe even if legacy data is corrupt.
    """
    rows = (
        await session.execute(
            select(Category.id, Category.parent_id).where(Category.user_id == user_id)
        )
    ).all()

    children: dict[uuid.UUID, list[uuid.UUID]] = {category_id: [] for category_id, _ in rows}
    for category_id, parent_id in rows:
        if parent_id is not None and parent_id in children:
            children[parent_id].append(category_id)

    subtrees: dict[uuid.UUID, frozenset[uuid.UUID]] = {}
    for root in children:
        seen: set[uuid.UUID] = set()
        stack = [root]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(children.get(current, ()))
        subtrees[root] = frozenset(seen)

    return subtrees
