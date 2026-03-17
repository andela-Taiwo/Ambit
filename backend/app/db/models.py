"""ORM models.

Phase 0 defines only `SchemaMetadata`, which records which application version
last migrated this database -- useful for verifying a deploy actually shipped
the migration it claimed. Domain models arrive in Phase 1.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchemaMetadata(Base):
    __tablename__ = "schema_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
