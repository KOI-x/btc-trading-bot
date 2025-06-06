from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
import requests

import models
from data_ingestion import historic_fetcher
from data_ingestion.historic_fetcher import ingest_price_history


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def fake_get_factory():
    coingecko_data = {
        "prices": [
            [1704067200000, 30000.0],
            [1704153600000, 31000.0],
        ]
    }
    fx_data = {
        "rates": {
            "2024-01-01": {"CLP": 900.0, "EUR": 0.9},
            "2024-01-02": {"CLP": 905.0, "EUR": 0.91},
        }
    }

    def fake_get(url, params=None, timeout=10):
        if "coingecko" in url:
            return FakeResponse(coingecko_data)
        if "exchangerate.host" in url:
            return FakeResponse(fx_data)
        raise RuntimeError("Unexpected URL")

    return fake_get


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.engine = engine
    models.SessionLocal = sessionmaker(bind=engine)
    models.init_db()
    monkeypatch.setattr(historic_fetcher, "SessionLocal", models.SessionLocal)
    monkeypatch.setattr(historic_fetcher, "init_db", models.init_db)
    monkeypatch.setattr(requests, "get", fake_get_factory())
    yield


def test_ingestion_with_fx(db):
    ingest_price_history("bitcoin")
    # running again should not duplicate
    ingest_price_history("bitcoin")

    with models.SessionLocal() as session:
        rows = session.query(models.PriceHistory).order_by(models.PriceHistory.date).all()
        assert len(rows) == 2
        assert rows[0].price_clp == pytest.approx(30000.0 * 900.0)
        assert rows[0].price_eur == pytest.approx(30000.0 * 0.9)
        assert rows[1].price_clp == pytest.approx(31000.0 * 905.0)
        assert rows[1].price_eur == pytest.approx(31000.0 * 0.91)

