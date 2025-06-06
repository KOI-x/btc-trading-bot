import os
import sys

BASE_DIR = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "..")))  # noqa: E402

from datetime import date  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from storage.database import (  # noqa: E402
    PriceHistory,
    get_price_on,
    ingest_price_history,
    init_db,
    init_engine,
)


def _rates(_: date) -> dict[str, Decimal]:
    return {"CLP": Decimal("900"), "EUR": Decimal("0.9")}


@pytest.fixture()
def session():
    """Create a fresh in-memory database for each test."""
    engine = init_engine("sqlite:///:memory:")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


def test_ingest_creates_record(session):
    """Records should be inserted correctly."""
    ingest_price_history(session, "btc", date(2024, 1, 1), 50_000.0, rates_fn=_rates)
    assert session.query(PriceHistory).count() == 1


def test_no_duplicate_insert(session):
    """Duplicate coin_id/date combinations should not create new rows."""
    ingest_price_history(session, "btc", date(2024, 1, 1), 50_000.0, rates_fn=_rates)
    ingest_price_history(session, "btc", date(2024, 1, 1), 60_000.0, rates_fn=_rates)
    assert session.query(PriceHistory).count() == 1
    # The stored price remains the updated one
    assert session.query(PriceHistory).one().price_usd == 60_000.0


def test_get_price_on_returns_value(session):
    """Querying by coin_id and date should return the expected price."""
    ingest_price_history(session, "btc", date(2024, 1, 1), 50_000.0, rates_fn=_rates)
    ingest_price_history(session, "btc", date(2024, 1, 2), 52_000.0, rates_fn=_rates)
    assert get_price_on(session, "btc", date(2024, 1, 2)) == 52_000.0


def test_get_price_on_missing(session):
    """If no record exists for the given date, None is returned."""
    assert get_price_on(session, "btc", date(2024, 1, 1)) is None
