import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from data_ingestion import exchangerate_client
from data_ingestion.errors import IngestionError
from storage.database import PriceHistory, ingest_price_history, init_db, init_engine


def _session():
    engine = init_engine("sqlite:///:memory:")
    init_db(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _rates(_: datetime.date) -> dict[str, Decimal]:
    return {"CLP": Decimal("900"), "EUR": Decimal("0.9")}


def test_get_rates_cached(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=10):
        calls.append(1)

        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"rates": {"CLP": 900.0, "EUR": 0.9}}

        return Resp()

    monkeypatch.setattr(exchangerate_client.requests, "get", fake_get)
    exchangerate_client._rates_cache.clear()

    d = datetime.date(2024, 1, 1)
    r1 = exchangerate_client.get_rates_for_date(d)
    r2 = exchangerate_client.get_rates_for_date(d)
    assert r1 == {"CLP": Decimal("900"), "EUR": Decimal("0.9")}
    assert r1 is r2
    assert len(calls) == 1


def test_ingest_stores_all_fiats():
    with _session() as session:
        ingest_price_history(
            session, "btc", datetime.date(2024, 1, 1), 100.0, rates_fn=_rates
        )
        rec = session.query(PriceHistory).one()
        assert rec.price_clp == 90000.0
        assert rec.price_eur == 90.0


def test_ingest_error_on_rates_failure():
    with _session() as session:

        def bad_rates(d):
            raise RuntimeError("boom")

        with pytest.raises(IngestionError):
            ingest_price_history(
                session, "btc", datetime.date(2024, 1, 1), 100.0, rates_fn=bad_rates
            )
