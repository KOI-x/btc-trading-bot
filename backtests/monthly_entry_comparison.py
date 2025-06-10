"""Compare monthly injection strategy vs DCA across different start dates."""

from __future__ import annotations

import argparse

# Add backtests directory to path so we can import from sibling modules
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

sys.path.append(str(Path(__file__).parent))  # noqa: E402

from monthly_injection_runner import (  # noqa: E402
    MonthlyInjectionBacktest,
    load_historical_data,
)


def simple_dca(
    df: pd.DataFrame, deposits: List[float], initial_usd: float = 0.0
) -> float:
    """Simulate buying BTC on the first day of each month with equal capital."""

    if df.empty:
        return 0.0

    btc_balance = 0.0
    deposit_idx = 0

    for _, row in df.iterrows():
        if row["Fecha"].day == 1:
            amount = 0.0
            if deposit_idx == 0 and initial_usd > 0:
                amount += initial_usd
            if deposit_idx < len(deposits):
                amount += deposits[deposit_idx]
            deposit_idx += 1
            if amount > 0:
                btc_balance += amount / row["Precio USD"]
    return btc_balance


def classify_cycle(start_price: float, end_price: float) -> str:
    """Return a simple classification of market cycle."""
    change = end_price / start_price
    if change >= 1.2:
        return "alcista"
    if change <= 0.8:
        return "bajista"
    return "lateral"


def evaluate_period(
    start: str,
    months: int,
    deposits: List[float],
    params: Dict[str, Any],
    initial_usd: float,
) -> Dict[str, Any]:
    df_all = load_historical_data()
    start_dt = pd.to_datetime(start)
    end_dt = start_dt + pd.DateOffset(months=months) - pd.DateOffset(days=1)
    df = df_all[(df_all["Fecha"] >= start_dt) & (df_all["Fecha"] <= end_dt)]
    if df.empty:
        raise ValueError("No hay datos para el periodo solicitado")
    backtest = MonthlyInjectionBacktest(initial_usd=initial_usd)
    result = backtest.run(df, params, deposits)
    dca_btc = simple_dca(df, deposits, initial_usd)
    final_price = result["final_price"]
    return {
        "periodo": start_dt.strftime("%Y-%m"),
        "ciclo": classify_cycle(df.iloc[0]["Precio USD"], final_price),
        "btc_estrategia": result["btc_accumulated"],
        "btc_dca": dca_btc,
        "diferencia_pct": (
            ((result["btc_accumulated"] / dca_btc) - 1) * 100 if dca_btc > 0 else 0
        ),
        "usd_final": result["final_usd"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara la estrategia de inyecciones mensuales contra DCA"
    )
    parser.add_argument("--start-dates", nargs="+", required=True)
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--initial-usd", type=float, default=0.0)
    parser.add_argument("--monthly", nargs="*", type=float, default=[])
    args = parser.parse_args()

    params = {
        "rsi_oversold": 30,
        "bollinger_oversold": 0.08,
        "atr_multiplier": 3.0,
        "risk_per_trade": 0.005,
        "min_rsi": 30,
        "trend_filter": False,
    }

    rows = []
    for start in args.start_dates:
        try:
            rows.append(
                evaluate_period(
                    start, args.months, args.monthly, params, args.initial_usd
                )
            )
        except ValueError as exc:
            print(f"Periodo {start} sin datos: {exc}")

    table = pd.DataFrame(rows)
    if not table.empty:
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
