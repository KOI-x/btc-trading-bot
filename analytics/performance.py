from __future__ import annotations

from datetime import datetime
from typing import Any, List

from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from storage.database import get_price_on, init_db, init_engine


def comparar_vs_hold(
    coin_id: str,
    fecha_inicio: str,
    fecha_fin: str,
    equity_curve: List[float],
    db_url: str = DATABASE_URL,
) -> dict[str, Any]:
    """Compara el rendimiento de una estrategia con la estrategia de buy & hold.

    Parameters
    ----------
    coin_id : str
        Identificador de la moneda a consultar.
    fecha_inicio : str
        Fecha inicial en formato ``YYYY-MM-DD``.
    fecha_fin : str
        Fecha final en formato ``YYYY-MM-DD``.
    equity_curve : list[float]
        Valores de capital simulados por la estrategia.
    db_url : str, optional
        URL de la base de datos SQLite.

    Returns
    -------
    dict
        Diccionario con ``retorno_hold``, ``retorno_estrategia`` y ``comparacion``.

    Raises
    ------
    ValueError
        Si faltan precios en la base de datos o ``equity_curve`` está vacía.
    """

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

    if not equity_curve:
        raise ValueError("equity_curve no puede estar vacía")
    retorno_estrategia = equity_curve[-1] / equity_curve[0] - 1

    if abs(retorno_estrategia - retorno_hold) < 1e-9:
        comparacion = "igual"
    elif retorno_estrategia > retorno_hold:
        comparacion = "mejor"
    else:
        comparacion = "peor"

    return {
        "retorno_hold": retorno_hold,
        "retorno_estrategia": retorno_estrategia,
        "comparacion": comparacion,
    }
