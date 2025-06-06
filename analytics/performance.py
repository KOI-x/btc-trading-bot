from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import sessionmaker

from storage.database import get_price_on, init_db, init_engine


def comparar_vs_hold(
    coin_id: str,
    fecha_inicio: str,
    fecha_fin: str,
    resultado_backtest: dict[str, Any],
    db_url: str = "sqlite:///prices.sqlite",
) -> dict[str, Any]:
    """Compara el retorno de una estrategia con un enfoque buy & hold."""

    start = datetime.fromisoformat(fecha_inicio).date()
    end = datetime.fromisoformat(fecha_fin).date()

    engine = init_engine(db_url)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        start_price = get_price_on(session, coin_id, start)
        end_price = get_price_on(session, coin_id, end)

    if start_price is None or end_price is None:
        raise ValueError("Faltan precios en la base de datos")

    retorno_hold = end_price / start_price - 1

    curva = resultado_backtest.get("equity_curve")
    if not curva:
        raise ValueError("resultado_backtest debe incluir 'equity_curve'")
    retorno_estrategia = curva[-1] / curva[0] - 1

    if abs(retorno_estrategia - retorno_hold) < 1e-9:
        comparacion = "igual"
    elif retorno_estrategia > retorno_hold:
        comparacion = "mejor"
    else:
        comparacion = "peor"

    return {
        "estrategia_vs_hold": comparacion,
        "retorno_estrategia": retorno_estrategia,
        "retorno_hold": retorno_hold,
    }
