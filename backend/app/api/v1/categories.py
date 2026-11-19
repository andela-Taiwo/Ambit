"""Category routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.categories import CategoryKind
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import CONFLICT, NOT_FOUND, UNAUTHORISED, Page
from app.services import categories as categories_service

router = APIRouter(prefix="/categories", tags=["categories"], responses=UNAUTHORISED)


@router.get("", response_model=Page[CategoryResponse], summary="List categories")
async def list_categories(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: CategoryKind | None = None,
    include_archived: bool = False,
) -> Page[CategoryResponse]:
    rows, total = await categories_service.list_categories(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        kind=kind,
        include_archived=include_archived,
    )
    return Page(
        items=[CategoryResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
    responses={**NOT_FOUND, **CONFLICT},
)
async def create_category(
    session: SessionDep, current_user: CurrentUser, payload: CategoryCreate
) -> CategoryResponse:
    category = await categories_service.create_category(session, current_user.id, payload)
    return CategoryResponse.model_validate(category)


@router.get(
    "/{category_id}", response_model=CategoryResponse, summary="Get a category", responses=NOT_FOUND
)
async def get_category(
    session: SessionDep, current_user: CurrentUser, category_id: uuid.UUID
) -> CategoryResponse:
    category = await categories_service.get_category(session, current_user.id, category_id)
    return CategoryResponse.model_validate(category)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category",
    responses={**NOT_FOUND, **CONFLICT},
)
async def update_category(
    session: SessionDep,
    current_user: CurrentUser,
    category_id: uuid.UUID,
    payload: CategoryUpdate,
) -> CategoryResponse:
    category = await categories_service.update_category(
        session, current_user.id, category_id, payload
    )
    return CategoryResponse.model_validate(category)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
    responses=NOT_FOUND,
)
async def delete_category(
    session: SessionDep, current_user: CurrentUser, category_id: uuid.UUID
) -> None:
    await categories_service.delete_category(session, current_user.id, category_id)
