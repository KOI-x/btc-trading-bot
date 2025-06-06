from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, Float, Integer, String

from .database import Base


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String, index=True)
    date = Column(Date)
    price_usd = Column(Float)


class Evaluation(Base):
    """Persisted record of a portfolio evaluation."""

    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    coin_id = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    input_data = Column(JSON, nullable=False)
    result_data = Column(JSON, nullable=False)
