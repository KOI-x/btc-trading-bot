"""Download historical prices and store them in SQLite."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

import requests
from sqlalchemy.exc import SQLAlchemyError

from models import PriceHistory, SessionLocal, init_db

FX_URL = "https://api.exchangerate.host/timeseries"


def fetch_fx_rates(dates: Iterable[date]) -> dict[date, dict[str, float]]:
    """Return USD to CLP/EUR rates for the given dates."""

    if not dates:
        return {}
    start = min(dates)
    end = max(dates)
    params = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "base": "USD",
        "symbols": "CLP,EUR",
    }
    try:
        resp = requests.get(FX_URL, params=params, timeout=10)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[ADVERTENCIA] Error al obtener tasas de cambio: {e}")
        return {}

    results: dict[date, dict[str, float]] = {}
    for key, rates in data.get("rates", {}).items():
        try:
            dt = date.fromisoformat(key)
        except ValueError:
            continue
        clp = rates.get("CLP")
        eur = rates.get("EUR")
        results[dt] = {"CLP": clp, "EUR": eur}
    return results


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
    dates = [datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date() for ts, _ in prices]
    fx_rates = fetch_fx_rates(dates)

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
        rate = fx_rates.get(date_val, {})
        price_clp = price * rate.get("CLP") if rate.get("CLP") is not None else None
        price_eur = price * rate.get("EUR") if rate.get("EUR") is not None else None
        record = PriceHistory(
            coin_id=coin_id,
            date=date_val,
            price_usd=price,
            price_clp=price_clp,
            price_eur=price_eur,
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
