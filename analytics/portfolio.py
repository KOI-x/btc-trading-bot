from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd
from sqlalchemy.orm import Session

from models import PriceHistory, SessionLocal, init_db


def _load_prices(
    session: Session, coin_id: str, start: date, end: date
) -> pd.DataFrame:
    """Devuelve un DataFrame con precios entre ``start`` y ``end``."""
    rows = (
        session.query(PriceHistory)
        .filter(
            PriceHistory.coin_id == coin_id,
            PriceHistory.date >= start,
            PriceHistory.date <= end,
        )
        .order_by(PriceHistory.date)
        .all()
    )
    data = [
        {
            "date": r.date,
            "price_usd": r.price_usd,
            "price_clp": r.price_clp,
        }
        for r in rows
    ]
    df = pd.DataFrame(data)
    if not df.empty:
        df.set_index("date", inplace=True)
    return df


def analizar_portafolio(operaciones: Iterable[dict]) -> pd.DataFrame:
    """Calcula el valor diario de un portafolio simulado.

    Parameters
    ----------
    operaciones : iterable de dict
        Lista de operaciones con ``coin_id``, ``date`` (YYYY-MM-DD) y ``amount``.

    Returns
    -------
    pandas.DataFrame
        DataFrame con columnas ``date``, ``total_value_usd``, ``total_value_clp``
        y una columna por cada moneda con su valor en USD.
    """
    ops_df = pd.DataFrame(list(operaciones))
    if ops_df.empty:
        return pd.DataFrame()

    ops_df["date"] = pd.to_datetime(ops_df["date"]).dt.date
    start = ops_df["date"].min()
    end = date.today()
    dates = pd.date_range(start, end, freq="D").date
    coins = sorted(ops_df["coin_id"].unique())

    init_db()
    with SessionLocal() as session:
        price_map = {coin: _load_prices(session, coin, start, end) for coin in coins}

    df_result = pd.DataFrame({"date": dates}).set_index("date")
    total_usd = pd.Series(0.0, index=dates)
    total_clp = pd.Series(0.0, index=dates, dtype=float)

    for coin in coins:
        price_df = price_map.get(coin)
        price_df = (
            price_df.reindex(dates, method="ffill")
            if not price_df.empty
            else pd.DataFrame(index=dates)
        )
        holdings = (
            ops_df[ops_df["coin_id"] == coin]
            .groupby("date")["amount"]
            .sum()
            .reindex(dates, fill_value=0)
            .cumsum()
        )
        usd_vals = holdings * price_df.get("price_usd")
        df_result[coin] = usd_vals
        total_usd += usd_vals.fillna(0)
        clp_series = price_df.get("price_clp")
        if clp_series is not None:
            clp_vals = holdings * clp_series
            total_clp += clp_vals.fillna(0)

    df_result["total_value_usd"] = total_usd
    df_result["total_value_clp"] = total_clp
    df_result.reset_index(inplace=True)
    cols = ["date", "total_value_usd", "total_value_clp"] + coins
    return df_result[cols]


if __name__ == "__main__":
    sample_ops = [
        {"coin_id": "bitcoin", "date": "2023-11-01", "amount": 0.05},
        {"coin_id": "ethereum", "date": "2023-12-10", "amount": 0.8},
    ]
    df = analizar_portafolio(sample_ops)
    print(df.tail())
