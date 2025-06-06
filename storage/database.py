from __future__ import annotations

from datetime import date

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

Base = declarative_base()


class PriceHistory(Base):
    """Historical price for a coin on a specific date."""

    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    coin_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    price = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("coin_id", "date", name="uix_coin_date"),)


def init_engine(url: str):
    """Create SQLAlchemy engine for the given URL."""
    return create_engine(url, echo=False, future=True)


def init_db(engine) -> None:
    """Create tables in the configured engine."""
    Base.metadata.create_all(engine)


def ingest_price_history(
    session: Session, coin_id: str, at: date, price: float
) -> PriceHistory:
    """Insert a price record if it does not already exist."""
    record = session.query(PriceHistory).filter_by(coin_id=coin_id, date=at).first()
    if record is None:
        record = PriceHistory(coin_id=coin_id, date=at, price=price)
        session.add(record)
        session.commit()
    return record


def get_price_on(session: Session, coin_id: str, at: date) -> float | None:
    """Retrieve the price for a coin on a specific date."""
    record = session.query(PriceHistory).filter_by(coin_id=coin_id, date=at).first()
    return record.price if record else None
