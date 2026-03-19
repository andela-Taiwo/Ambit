"""The committed OpenAPI schema is the frontend's contract.

These tests fail if the schema changes without `openapi.json` being
regenerated, so contract drift is caught in CI rather than at runtime in the
frontend (plan Section 2: a single source of truth for API contracts).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


@pytest.fixture
def committed_schema() -> dict[str, Any]:
    result: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return result


@pytest.fixture
def live_schema() -> dict[str, Any]:
    from app.main import create_app

    result: dict[str, Any] = create_app().openapi()
    return result


def test_committed_schema_matches_the_application(
    committed_schema: dict[str, Any], live_schema: dict[str, Any]
) -> None:
    assert committed_schema == live_schema, (
        "openapi.json is stale. Regenerate it with: uv run python scripts/export_openapi.py"
    )


def test_every_identified_resource_documents_a_404(live_schema: dict[str, Any]) -> None:
    missing = [
        f"{method.upper()} {path}"
        for path, operations in live_schema["paths"].items()
        if "{" in path
        for method, operation in operations.items()
        if "404" not in operation.get("responses", {})
    ]

    assert not missing, f"Routes taking an id must document a 404: {missing}"


def test_protected_routes_declare_security(live_schema: dict[str, Any]) -> None:
    public = {
        "/health",
        "/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    }

    unsecured = [
        f"{method.upper()} {path}"
        for path, operations in live_schema["paths"].items()
        if path not in public
        for method, operation in operations.items()
        if not operation.get("security")
    ]

    assert not unsecured, f"These routes must require authentication: {unsecured}"


def test_money_is_never_typed_as_a_float(live_schema: dict[str, Any]) -> None:
    """Plan Section 9: money is integer minor units or a decimal string."""
    offenders = []
    for name, schema in live_schema["components"]["schemas"].items():
        for field, spec in schema.get("properties", {}).items():
            if field.endswith("_minor") and spec.get("type") != "integer":
                offenders.append(f"{name}.{field}")

    assert not offenders, f"Minor-unit fields must be integers: {offenders}"
