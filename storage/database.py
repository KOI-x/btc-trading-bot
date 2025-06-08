from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from typing import Callable, Dict

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base

from analytics.s2f import calcular_desviacion, obtener_valor_s2f
from data_ingestion.errors import IngestionError
from data_ingestion.exchangerate_client import get_rates_for_date

Base = declarative_base()


class PriceHistory(Base):
    """Historical price for a coin on a specific date."""

    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    coin_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    price_usd = Column(Float, nullable=False)
    price_clp = Column(Float)
    price_eur = Column(Float)
    s2f_deviation = Column(Float)
    __table_args__ = (UniqueConstraint("coin_id", "date", name="uix_coin_date"),)


def init_engine(url: str):
    """Create SQLAlchemy engine for the given URL."""
    return create_engine(url, echo=False, future=True)


def init_db(engine) -> None:
    """Create tables in the configured engine."""
    Base.metadata.create_all(engine)


def ingest_price_history(
    session: Session,
    coin_id: str,
    at: date,
    price_usd: float,
    rates_fn: Callable[[date], Dict[str, Decimal]] | None = None,
) -> PriceHistory:
    """Insert or update a price record with multi-fiat support."""

    if rates_fn is None:
        rates_fn = get_rates_for_date

    # fetch conversion rates with retries
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            rates = rates_fn(at)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2**attempt)
    else:
        raise IngestionError(f"failed to fetch rates: {last_exc}")

    price_clp = float(Decimal(str(price_usd)) * rates["CLP"])
    price_eur = float(Decimal(str(price_usd)) * rates["EUR"])

    s2f_val = obtener_valor_s2f(at.isoformat())
    s2f_dev = calcular_desviacion(price_usd, s2f_val) if s2f_val is not None else None

    record = session.query(PriceHistory).filter_by(coin_id=coin_id, date=at).first()
    if record is None:
        record = PriceHistory(
            coin_id=coin_id,
            date=at,
            price_usd=price_usd,
            price_clp=price_clp,
            price_eur=price_eur,
            s2f_deviation=s2f_dev,
        )
        session.add(record)
    else:
        record.price_usd = price_usd
        record.price_clp = price_clp
        record.price_eur = price_eur
        record.s2f_deviation = s2f_dev
    session.commit()
    return record


def get_price_on(session: Session, coin_id: str, at: date) -> float | None:
    """Retrieve the price for a coin on a specific date."""
    record = session.query(PriceHistory).filter_by(coin_id=coin_id, date=at).first()
    return record.price_usd if record else None


def get_price_history_df(session: Session, coin_id: str) -> pd.DataFrame:
    """Return historical prices for a coin as DataFrame."""
    rows = (
        session.query(PriceHistory)
        .filter(PriceHistory.coin_id == coin_id)
        .order_by(PriceHistory.date)
        .all()
    )
    data = [
        {
            "Fecha": r.date,
            "Precio USD": r.price_usd,
            "Desviación S2F %": r.s2f_deviation,
        }
        for r in rows
    ]
    df = pd.DataFrame(data)
    if not df.empty:
        df["Variación %"] = df["Precio USD"].pct_change() * 100
        df["Variación %"] = df["Variación %"].fillna(0)
    return df
