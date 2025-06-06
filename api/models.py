from sqlalchemy import Column, Date, Float, Integer, String

from .database import Base


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String, index=True)
    date = Column(Date)
    price_usd = Column(Float)
