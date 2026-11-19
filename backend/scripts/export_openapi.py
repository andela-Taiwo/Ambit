"""Export the OpenAPI schema to `openapi.json`.

Committed so the frontend's generated client and any contract diff are visible
in review (plan Section 13: regenerate and commit if the API changed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# The schema is derived from route/model definitions, so any syntactically
# valid config will do -- nothing here connects to a database.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
os.environ.setdefault("SECRET_KEY", "openapi-export-placeholder-key")
os.environ.setdefault("APP_ENV", "local")

from app.main import create_app

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths = len(schema.get("paths", {}))
    print(f"Wrote {OUTPUT} ({paths} paths)")


if __name__ == "__main__":
    main()
