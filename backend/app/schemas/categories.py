"""Category request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.domain.categories import CategoryKind
from app.schemas.common import ORMModel

CategoryName = Annotated[str, Field(min_length=1, max_length=120)]


class CategoryCreate(BaseModel):
    name: CategoryName
    kind: CategoryKind
    parent_id: uuid.UUID | None = None


class CategoryUpdate(BaseModel):
    name: CategoryName | None = None
    parent_id: uuid.UUID | None = None
    is_archived: bool | None = None


class CategoryResponse(ORMModel):
    id: uuid.UUID
    name: str
    kind: CategoryKind
    parent_id: uuid.UUID | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
