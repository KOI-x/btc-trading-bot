import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from typing import Dict

BASE_DIR = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "..")))  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from analytics.performance import comparar_vs_hold  # noqa: E402
from storage.database import ingest_price_history  # noqa: E402
from storage.database import init_db, init_engine  # noqa: E402


def _rates(_: date) -> Dict[str, Decimal]:
    return {"CLP": Decimal("900"), "EUR": Decimal("0.9")}


def _prepare_db() -> tuple[str, sessionmaker]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    url = f"sqlite:///{tmp.name}"
    engine = init_engine(url)
    init_db(engine)
    return url, sessionmaker(bind=engine)


def test_comparar_vs_hold_mejor():
    url, Session = _prepare_db()
    with Session() as session:
        ingest_price_history(
            session,
            "btc",
            date(2024, 1, 1),
            100.0,
            rates_fn=_rates,
        )
        ingest_price_history(
            session,
            "btc",
            date(2024, 1, 2),
            120.0,
            rates_fn=_rates,
        )

    result = comparar_vs_hold(
        "btc",
        "2024-01-01",
        "2024-01-02",
        [1.0, 1.3],
        db_url=url,
    )
    assert result["comparacion"] == "mejor"
    assert result["retorno_hold"] == pytest.approx(0.2)
    assert result["retorno_estrategia"] == pytest.approx(0.3)


def test_comparar_vs_hold_peor():
    url, Session = _prepare_db()
    with Session() as session:
        ingest_price_history(
            session,
            "btc",
            date(2024, 1, 1),
            100.0,
            rates_fn=_rates,
        )
        ingest_price_history(
            session,
            "btc",
            date(2024, 1, 2),
            110.0,
            rates_fn=_rates,
        )

    result = comparar_vs_hold(
        "btc",
        "2024-01-01",
        "2024-01-02",
        [1.0, 1.05],
        db_url=url,
    )
    assert result["comparacion"] == "peor"
