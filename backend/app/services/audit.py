"""Append-only audit trail for financial mutations.

Audit rows join the same transaction as the change they describe, so a rollback
cannot leave a log entry claiming a mutation that never committed. `request_id`
is copied from the logging context, linking the trail to the HTTP request.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import request_id_ctx
from app.db.models import AuditLog


def record(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            request_id=request_id_ctx.get(),
        )
    )
