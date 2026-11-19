"""Daily recurring-transaction materialisation job.

Run from cron/day-scheduler: `python -m app.jobs.run_recurring`. It is safe to
run more than once: generated rows are unique per (rule, occurrence) and the
cursor only advances over occurrences that were emitted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, session_scope
from app.services.recurring import run_all_due

logger = get_logger(__name__)


async def run(as_of: date | None = None) -> tuple[int, int]:
    """Return (rules processed, transactions generated)."""
    effective_as_of = as_of or datetime.now(UTC).date()
    async with session_scope() as session:
        summaries = await run_all_due(session, as_of=effective_as_of)

    generated = sum(summary.generated_count for summary in summaries)
    for summary in summaries:
        logger.info(
            "recurring_rule_run",
            rule_id=str(summary.rule_id),
            generated=summary.generated_count,
            skipped=summary.skipped_count,
            next_run_on=summary.next_run_on.isoformat(),
        )
    return len(summaries), generated


async def main(argv: Sequence[str] | None = None) -> int:
    del argv  # CLI arguments are intentionally not accepted; behaviour is env-driven.
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.app_env != "local")
    try:
        rules, generated = await run()
    except Exception as exc:
        logger.error("recurring_job_failed", error=str(exc))
        return 1
    finally:
        await dispose_engine()

    logger.info("recurring_job_complete", rules=rules, generated=generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
