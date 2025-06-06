from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent


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
        return

    print(f"\U0001f331 Cargando datos desde {csv_path} ...")
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
    print("✅ Datos iniciales cargados")


def ensure_database() -> None:
    """Create database file and tables if needed."""
    from api.database import Base, engine
    from config import DATABASE_URL

    db_path = _sqlite_path(DATABASE_URL)
    first_time = False
    if db_path and not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        first_time = True

    Base.metadata.create_all(bind=engine)

    if first_time:
        print("✅ DB creada")
        seed_prices()


def main() -> None:
    load_dotenv()
    ensure_database()
    print("🚀 Servidor corriendo en http://localhost:8000")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
