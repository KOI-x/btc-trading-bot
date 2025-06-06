from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy.orm import sessionmaker

from analytics.performance import comparar_vs_hold
from backtests.ema_s2f_backtest import run_backtest
from config import DATABASE_URL
from storage.database import get_price_on, init_db, init_engine


def evaluate_request(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process portfolio evaluation request and return per-coin results."""
    portfolio = input_data.get("portfolio", [])
    strategy = input_data.get("strategy")
    if strategy != "ema_s2f":
        raise ValueError("Unsupported strategy")
    if not portfolio:
        raise ValueError("Portfolio cannot be empty")

    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    results: List[Dict[str, Any]] = []
    initial_total = 0.0
    final_hold_total = 0.0
    final_strategy_total = 0.0
    for item in portfolio:
        coin_id = item["coin_id"]
        amount = float(item["amount"])
        buy_date = item["buy_date"]
        if isinstance(buy_date, str):
            buy_date = datetime.fromisoformat(buy_date).date()

        with Session() as session:
            start_price = get_price_on(session, coin_id, buy_date)
            end_price = get_price_on(session, coin_id, date.today())
        if start_price is None or end_price is None:
            raise ValueError("Missing price data")

        initial_cap = amount * start_price
        initial_total += initial_cap
        final_hold_total += amount * end_price

        result = run_backtest(coin_id, initial_cap, buy_date.isoformat())
        cmp_result = comparar_vs_hold(
            coin_id,
            buy_date.isoformat(),
            date.today().isoformat(),
            result["equity_curve"],
        )
        final_strategy_total += initial_cap * (1 + cmp_result["retorno_estrategia"])
        diff_pct = (cmp_result["retorno_estrategia"] - cmp_result["retorno_hold"]) * 100
        if diff_pct > 0:
            comentario = f"Tu estrategia supera al hold en un {diff_pct:.0f}%"
        elif diff_pct < 0:
            comentario = f"Hold era mejor por {abs(diff_pct):.0f}%"
        else:
            comentario = "La estrategia obtuvo el mismo retorno que holdear"
        results.append(
            {
                "coin_id": coin_id,
                "estrategia": strategy,
                "fecha": buy_date.isoformat(),
                "retorno_estrategia": cmp_result["retorno_estrategia"],
                "retorno_hold": cmp_result["retorno_hold"],
                "comparacion": cmp_result["comparacion"],
                "equity_curve": result["equity_curve"],
                "comentario": comentario,
            }
        )

    retorno_hold = final_hold_total / initial_total - 1
    retorno_estrategia = final_strategy_total / initial_total - 1

    if abs(retorno_estrategia - retorno_hold) < 1e-9:
        comparacion = "igual"
    elif retorno_estrategia > retorno_hold:
        comparacion = "mejor"
    else:
        comparacion = "peor"

    diff_pct = (retorno_estrategia - retorno_hold) * 100
    if diff_pct > 0:
        sugerencia = f"Tu estrategia supera al hold en un {diff_pct:.0f}%"
    elif diff_pct < 0:
        sugerencia = f"Hold era mejor por {abs(diff_pct):.0f}%"
    else:
        sugerencia = "La estrategia obtuvo el mismo retorno que holdear"

    return {"results": results, "suggestion": sugerencia, "comparacion": comparacion}
