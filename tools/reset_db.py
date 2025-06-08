#!/usr/bin/env python
"""Reset database by deleting existing file and running migrations."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

from config import DATABASE_URL

ROOT_DIR = Path(__file__).resolve().parents[1]


def _sqlite_path(url: str) -> Path | None:
    prefix = "sqlite:///"
    if url.startswith(prefix) and url != "sqlite:///:memory:":
        db_path = Path(url[len(prefix) :])
        if not db_path.is_absolute():
            db_path = ROOT_DIR / db_path
        return db_path
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset database")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing database file without asking",
    )
    args = parser.parse_args()

    db_path = _sqlite_path(DATABASE_URL)
    if db_path and db_path.exists():
        if args.force or input(f"Delete {db_path}? [y/N] ").lower().startswith("y"):
            db_path.unlink()
            print(f"\u2705 Removed {db_path}")
        else:
            print("Aborted")
            return

    subprocess.run(["alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    main()
