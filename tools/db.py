#!/usr/bin/env python
"""Utility commands for database setup and migrations."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from api.database import Base as ApiBase
from api.database import engine as api_engine
from config import DATABASE_URL
from storage.database import Base as StorageBase

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _sqlite_path(url: str) -> Path | None:
    prefix = "sqlite:///"
    if url.startswith(prefix) and url != "sqlite:///:memory:":
        db_path = Path(url[len(prefix) :])
        if not db_path.is_absolute():
            db_path = ROOT_DIR / db_path
        return db_path
    return None


def init_db() -> None:
    """Create the database file and run migrations if needed."""
    db_path = _sqlite_path(DATABASE_URL)
    if db_path and not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    upgrade_db()
    _ensure_tables()


def _alembic_cfg() -> Config:
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return cfg


def _has_migrations() -> bool:
    return any((ROOT_DIR / "migrations" / "versions").glob("*.py"))


def upgrade_db() -> None:
    """Apply pending Alembic migrations if any exist."""
    if not _has_migrations():
        logging.info("No Alembic migrations detected; skipping upgrade")
        return
    command.upgrade(_alembic_cfg(), "head")


def _ensure_tables() -> None:
    """Create required tables if missing."""
    inspector = inspect(api_engine)
    required = ["prices", "evaluations", "price_history"]
    missing = [t for t in required if not inspector.has_table(t)]
    if missing:
        logging.info("Creating missing tables: %s", ", ".join(missing))
        ApiBase.metadata.create_all(bind=api_engine)
        StorageBase.metadata.create_all(bind=api_engine)


def main() -> None:
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
