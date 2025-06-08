"""Download historical prices and store them in SQLite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests
from sqlalchemy.exc import SQLAlchemyError

from storage.database import SessionLocal, init_db, ingest_price_history, PriceHistory


def _daterange(start: datetime, end: datetime) -> Iterable[datetime]:
    """Yield UTC datetime values from ``start`` to ``end`` with day steps."""

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def download_price_history(coin_id: str) -> None:
    """Download last 90 days of price data for ``coin_id`` and store it.

    Existing records for the same coin and date are not duplicated and cached
    records are not re-downloaded.
    """

    init_db()
    session = SessionLocal()

    end_date = datetime.now(tz=timezone.utc).date()
    start_date = end_date - timedelta(days=89)

    # Collect already cached dates in the requested range
    cached_dates = {
        r.date
        for r in session.query(PriceHistory.date)
        .filter(PriceHistory.coin_id == coin_id)
        .filter(PriceHistory.date.between(start_date, end_date))
    }

    # Build list of missing dates
    missing_dates = [
        d.date()
        for d in _daterange(
            datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
            datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        if d.date() not in cached_dates
    ]

    if not missing_dates:
        print("[INFO] Todos los precios ya existen en la base de datos.")
        session.close()
        return

    fetch_start = min(missing_dates)
    fetch_end = max(missing_dates) + timedelta(days=1)

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {
        "vs_currency": "usd",
        "from": int(
            datetime.combine(
                fetch_start, datetime.min.time(), tzinfo=timezone.utc
            ).timestamp()
        ),
        "to": int(
            datetime.combine(
                fetch_end, datetime.min.time(), tzinfo=timezone.utc
            ).timestamp()
        ),
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[ADVERTENCIA] Error al obtener datos de {coin_id}: {e}")
        session.close()
        return

    prices = data.get("prices", [])

    date_to_price: dict[datetime.date, float] = {}
    for ts, price in prices:
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        if start_date <= day <= end_date:
            date_to_price[day] = price

    for day in sorted(date_to_price):
        price = date_to_price[day]
        if day in cached_dates:
            print(f"[CACHE] {day} ya almacenado, se omite")
            continue

        ingest_price_history(session, coin_id, day, price)
        print(f"[DESCARGADO] {day} guardado en la base de datos")

    try:
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[ADVERTENCIA] Error al guardar en la base de datos: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    download_price_history("bitcoin")
