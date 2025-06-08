from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from storage.database import PriceHistory, init_engine
from tools.db import init_db

logging.basicConfig(level=logging.INFO, format="%(message)s")

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "price_history"


def _load_csv(session, path: Path) -> None:
    coin_id = path.stem
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    for i, row in df.iterrows():
        exists = (
            session.query(PriceHistory)
            .filter_by(coin_id=coin_id, date=row["date"])
            .first()
        )
        if exists:
            continue
        record = PriceHistory(
            coin_id=coin_id,
            date=row["date"],
            price_usd=float(row["price"]),
        )
        session.add(record)
        if (i + 1) % 500 == 0:
            logging.info("%s: %d registros", coin_id, i + 1)
            session.flush()
    session.commit()
    logging.info("%s: cargado %d registros", coin_id, len(df))


def main() -> None:
    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        for csv_file in sorted(FIXTURES_DIR.glob("*.csv")):
            logging.info("Cargando %s", csv_file.name)
            _load_csv(session, csv_file)
    finally:
        session.close()


if __name__ == "__main__":
    main()
