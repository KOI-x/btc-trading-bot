from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _sqlite_path(url: str) -> Path | None:
    """Return Path for sqlite file or ``None`` for other schemes."""
    prefix = "sqlite:///"
    if url.startswith(prefix) and url != "sqlite:///:memory:":
        db_path = Path(url[len(prefix) :])
        if not db_path.is_absolute():
            db_path = ROOT_DIR / db_path
        return db_path
    return None


def seed_prices() -> None:
    """Load initial price data from ``fixtures/seed_prices.csv`` if present."""
    from api.database import SessionLocal
    from api.models import Price

    csv_path = ROOT_DIR / "fixtures" / "seed_prices.csv"
    if not csv_path.exists():
        logging.info("No seed data file found: %s", csv_path)
        return

    logging.info("\U0001f331 Cargando datos desde %s ...", csv_path)
    with SessionLocal() as session, open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            session.add(
                Price(
                    coin_id=row["coin_id"],
                    date=datetime.fromisoformat(row["date"]).date(),
                    price_usd=float(row["price_usd"]),
                )
            )
        session.commit()
    logging.info("✅ Datos iniciales cargados")


def ensure_database() -> None:
    """Ensure DB exists and apply migrations."""
    from tools.db import init_db

    logging.info("Inicializando base de datos si es necesario...")
    init_db()
    seed_prices()


def main() -> None:
    load_dotenv()
    try:
        ensure_database()
    except Exception as exc:  # noqa: BLE001
        logging.exception("Error al preparar la base de datos: %s", exc)
        return

    logging.info("🚀 Servidor corriendo en http://localhost:8000")
    try:
        uvicorn.run("api.main:app", host="0.0.0.0", port=8000)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Fallo del servidor: %s", exc)


if __name__ == "__main__":
    main()
