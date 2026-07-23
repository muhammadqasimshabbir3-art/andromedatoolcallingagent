#!/usr/bin/env python3
"""Export the live Neon Solar Store schema into agent data files.

Usage (from repo root):
    python scripts/export_store_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from agent.custom_tools.database_tools import (  # noqa: E402
    refresh_store_schema,
    store_schema_path,
)


def main() -> int:
    text = refresh_store_schema()
    path = store_schema_path()
    print(f"Schema refreshed ({len(text)} chars)")
    print(f"Primary file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
