"""Category hierarchy rules (plan Section 9: `Transport > Fuel`)."""

from __future__ import annotations

import uuid

import pytest

from app.domain.categories import (
    DEFAULT_CATEGORIES,
    MAX_CATEGORY_DEPTH,
    CategoryCycleError,
    CategoryDepthError,
    CategoryKind,
    validate_parent_assignment,
)


class TestValidateParentAssignment:
    def test_a_root_category_is_allowed(self) -> None:
        validate_parent_assignment(category_id=uuid.uuid4(), parent_id=None, ancestor_ids=[])

    def test_a_child_of_a_root_is_allowed(self) -> None:
        parent = uuid.uuid4()
        validate_parent_assignment(
            category_id=uuid.uuid4(), parent_id=parent, ancestor_ids=[parent]
        )

    def test_a_category_cannot_be_its_own_parent(self) -> None:
        category_id = uuid.uuid4()

        with pytest.raises(CategoryCycleError):
            validate_parent_assignment(
                category_id=category_id, parent_id=category_id, ancestor_ids=[category_id]
            )

    def test_a_category_cannot_be_parented_to_its_own_descendant(self) -> None:
        """Reparenting Transport under Transport>Fuel would orphan the tree."""
        category_id = uuid.uuid4()
        descendant = uuid.uuid4()

        with pytest.raises(CategoryCycleError):
            validate_parent_assignment(
                category_id=category_id,
                parent_id=descendant,
                ancestor_ids=[descendant, category_id],
            )

    def test_depth_within_the_limit_is_allowed(self) -> None:
        ancestors = [uuid.uuid4() for _ in range(MAX_CATEGORY_DEPTH - 1)]
        validate_parent_assignment(
            category_id=uuid.uuid4(), parent_id=ancestors[0], ancestor_ids=ancestors
        )

    def test_exceeding_the_depth_limit_is_rejected(self) -> None:
        ancestors = [uuid.uuid4() for _ in range(MAX_CATEGORY_DEPTH)]

        with pytest.raises(CategoryDepthError):
            validate_parent_assignment(
                category_id=uuid.uuid4(), parent_id=ancestors[0], ancestor_ids=ancestors
            )


class TestDefaultCategories:
    def test_includes_both_income_and_expense_categories(self) -> None:
        kinds = {kind for _, kind, _ in DEFAULT_CATEGORIES}

        assert kinds == {CategoryKind.INCOME, CategoryKind.EXPENSE}

    def test_top_level_names_are_unique(self) -> None:
        names = [name for name, _, _ in DEFAULT_CATEGORIES]

        assert len(names) == len(set(names))

    def test_child_names_are_unique_within_each_parent(self) -> None:
        for _, _, children in DEFAULT_CATEGORIES:
            assert len(children) == len(set(children))

    def test_nesting_stays_within_the_depth_limit(self) -> None:
        """Seed data must satisfy the same rules as user-created categories."""
        assert all(
            len(children) == 0 or MAX_CATEGORY_DEPTH >= 2 for _, _, children in DEFAULT_CATEGORIES
        )

    def test_transport_has_a_fuel_subcategory(self) -> None:
        """The plan's worked example of a hierarchy."""
        transport = next(
            children for name, _, children in DEFAULT_CATEGORIES if name == "Transport"
        )

        assert "Fuel" in transport
