"""Download historical prices and store them in SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy.exc import SQLAlchemyError

from models import PriceHistory, SessionLocal, init_db


def ingest_price_history(coin_id: str) -> None:
    """Download last 90 days of price data for ``coin_id`` and store it.

    Existing records for the same coin and date are not duplicated.
    """

    init_db()
    session = SessionLocal()

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "90", "interval": "daily"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[ADVERTENCIA] Error al obtener datos de {coin_id}: {e}")
        session.close()
        return

    prices = data.get("prices", [])
    prev_price = None
    for ts, price in prices:
        date_val = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        if (
            session.query(PriceHistory)
            .filter_by(coin_id=coin_id, date=date_val)
            .first()
        ):
            prev_price = price
            continue
        pct_change = None
        if prev_price is not None and prev_price != 0:
            pct_change = (price - prev_price) / prev_price * 100
        record = PriceHistory(
            coin_id=coin_id,
            date=date_val,
            price_usd=price,
            pct_change_24h=pct_change,
        )
        session.add(record)
        prev_price = price

    try:
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[ADVERTENCIA] Error al guardar en la base de datos: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    ingest_price_history("bitcoin")
