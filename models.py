from sqlalchemy import (
    Column,
    Date,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///database.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    coin_id = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    price_usd = Column(Float, nullable=False)
    price_clp = Column(Float)
    pct_change_24h = Column(Float)
    s2f_deviation = Column(Float)

    _coin_date_uc = UniqueConstraint("coin_id", "date", name="uix_coin_date")
    __table_args__ = (_coin_date_uc,)


def init_db() -> None:
    """Create tables if they do not exist."""
    Base.metadata.create_all(engine)
