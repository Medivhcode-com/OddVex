#!/usr/bin/env python
"""Write the OpenAPI schema to ``services/api/openapi.json``.

Deterministic (sorted keys, fixed settings, trailing newline) so CI can diff it:

    python scripts/export_openapi.py && git diff --exit-code -- openapi.json

``--check`` exits 1 if the committed file is out of date instead of rewriting it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from oddvex_api.config import Settings
from oddvex_api.main import create_app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    # Explicit settings so the schema never depends on the caller's environment or .env file.
    settings = Settings(_env_file=None, env="development", database_url="sqlite://")  # type: ignore[call-arg]
    schema = create_app(settings).openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    rendered = render()
    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            print(f"{OUTPUT} is out of date; run scripts/export_openapi.py", file=sys.stderr)
            return 1
        print(f"{OUTPUT} is up to date")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
