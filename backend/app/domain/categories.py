"""Category hierarchy rules.

Categories form a shallow tree (`Transport > Fuel`). Depth is capped and cycles
are rejected: an unbounded or cyclic tree turns every reporting query in Phase
3 and 5 into a potential infinite walk.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

#: Maximum ancestors a category may have. Two levels covers the planned
#: `Parent > Child` shape with room to spare, without inviting deep trees.
MAX_CATEGORY_DEPTH: Final = 3


class CategoryKind(StrEnum):
    """Whether a category classifies money coming in or going out."""

    INCOME = "income"
    EXPENSE = "expense"


class CategoryError(Exception):
    """Base class for category domain errors."""


class CategoryCycleError(CategoryError):
    """The requested parent would create a cycle."""


class CategoryDepthError(CategoryError):
    """The requested parent would exceed the maximum nesting depth."""


def validate_parent_assignment(
    *,
    category_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    ancestor_ids: Sequence[uuid.UUID],
) -> None:
    """Validate moving `category_id` under `parent_id`.

    `ancestor_ids` is the prospective parent's ancestor chain, including the
    parent itself. Callers resolve it from the database; keeping the walk out
    of this function leaves the rule itself pure and directly testable.
    """
    if parent_id is None:
        return

    if parent_id == category_id or category_id in ancestor_ids:
        raise CategoryCycleError(
            "A category cannot be nested under itself or one of its descendants"
        )

    if len(ancestor_ids) >= MAX_CATEGORY_DEPTH:
        raise CategoryDepthError(f"Category nesting is limited to {MAX_CATEGORY_DEPTH} levels")


#: Starter categories created for every new user. They are ordinary rows the
#: user can rename, archive or delete -- seeding only avoids an empty app on
#: first login, and gives Phase 3 budgets something to attach to.
DEFAULT_CATEGORIES: Final[tuple[tuple[str, CategoryKind, tuple[str, ...]], ...]] = (
    ("Salary", CategoryKind.INCOME, ()),
    ("Other Income", CategoryKind.INCOME, ()),
    ("Housing", CategoryKind.EXPENSE, ("Rent/Mortgage", "Utilities", "Council Tax")),
    ("Groceries", CategoryKind.EXPENSE, ()),
    ("Transport", CategoryKind.EXPENSE, ("Fuel", "Public Transport")),
    ("Eating Out", CategoryKind.EXPENSE, ()),
    ("Health", CategoryKind.EXPENSE, ()),
    ("Subscriptions", CategoryKind.EXPENSE, ()),
    ("Savings & Investments", CategoryKind.EXPENSE, ()),
    ("Other", CategoryKind.EXPENSE, ()),
)
