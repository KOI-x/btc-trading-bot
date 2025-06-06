from pathlib import Path

import pandas as pd
from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_FILE = Path("prices.sqlite")
engine = create_engine(f"sqlite:///{DB_FILE}")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    date = Column(String, index=True, nullable=False)
    coin_id = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    s2f_deviation = Column(Float)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_price_history_df(coin_id: str) -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = (
            session.query(PriceHistory)
            .filter(PriceHistory.coin_id == coin_id)
            .order_by(PriceHistory.date)
            .all()
        )
        data = [
            {
                "Fecha": r.date,
                "Precio USD": r.price,
                "Desviación S2F %": r.s2f_deviation,
            }
            for r in rows
        ]
    finally:
        session.close()

    df = pd.DataFrame(data)
    if not df.empty:
        df["Variación %"] = df["Precio USD"].pct_change() * 100
        df["Variación %"].fillna(0, inplace=True)
    return df
