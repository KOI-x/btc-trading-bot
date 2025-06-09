#!/usr/bin/env python
"""Utility commands for database setup and migrations."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

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


def init_db(engine=None) -> None:
    """Create the database file and run migrations if needed."""
    if engine is None:
        db_path = _sqlite_path(DATABASE_URL)
        if db_path and not db_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
    upgrade_db()


def upgrade_db() -> None:
    """Apply pending Alembic migrations."""
    subprocess.run(["alembic", "upgrade", "head"], check=True)


def main() -> None:
    """Handle command line interface for database utilities."""
    parser = argparse.ArgumentParser(description="Database utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Initialize database if empty and upgrade")
    sub.add_parser("upgrade", help="Apply migrations")
    args = parser.parse_args()

    if args.cmd == "init":
        init_db()
    elif args.cmd == "upgrade":
        upgrade_db()


if __name__ == "__main__":
    main()
