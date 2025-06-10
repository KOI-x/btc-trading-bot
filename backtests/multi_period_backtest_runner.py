from __future__ import annotations

"""Run monthly injection backtest over multiple periods and compare with DCA."""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

# Add backtests directory to path so we can import sibling modules
sys.path.append(str(Path(__file__).parent))  # noqa: E402

from monthly_entry_comparison import classify_cycle, simple_dca  # noqa: E402
from monthly_injection_runner import (  # noqa: E402
    MonthlyInjectionBacktest,
    load_historical_data,
)

DEFAULT_PERIODS: List[Tuple[str, str]] = [
    ("2017-01-01", "2017-12-31"),
    ("2017-01-01", "2018-12-31"),
    ("2019-01-01", "2020-12-31"),
    ("2020-03-01", "2021-03-31"),
    ("2021-01-01", "2022-12-31"),
    ("2023-01-01", "2024-06-01"),
    ("2017-01-01", "2024-06-01"),
]


def run_period(
    start: str, end: str, deposits: List[float], params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute the strategy and DCA baseline for a single period."""
    df_all = load_historical_data()
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    df = df_all[(df_all["Fecha"] >= start_dt) & (df_all["Fecha"] <= end_dt)]

    if df.empty:
        return {
            "periodo": f"{start} - {end}",
            "ciclo": "sin datos",
            "btc_estrategia": 0.0,
            "btc_dca": 0.0,
            "usd_estrategia": 0.0,
            "usd_dca": 0.0,
            "diferencia_pct": 0.0,
            "señales_disparadas": 0,
        }

    backtest = MonthlyInjectionBacktest(initial_usd=0)
    result = backtest.run(df, params, deposits)

    dca_btc = simple_dca(df, deposits)
    final_price = result["final_price"]
    dca_usd = dca_btc * final_price

    return {
        "periodo": f"{start} - {end}",
        "ciclo": classify_cycle(df.iloc[0]["Precio USD"], final_price),
        "btc_estrategia": result["btc_accumulated"],
        "btc_dca": dca_btc,
        "usd_estrategia": result["final_usd"],
        "usd_dca": dca_usd,
        "diferencia_pct": (
            ((result["btc_accumulated"] / dca_btc) - 1) * 100 if dca_btc > 0 else 0
        ),
        "señales_disparadas": result.get(
            "signals_triggered", len(result.get("trades", []))
        ),
    }


def parse_periods(args_periods: List[str] | None) -> List[Tuple[str, str]]:
    """Parse CLI periods into a list of tuples."""
    if not args_periods:
        return DEFAULT_PERIODS
    if len(args_periods) % 2 != 0:
        raise ValueError("Debe indicar pares de fechas inicio y fin")
    return [
        (args_periods[i], args_periods[i + 1]) for i in range(0, len(args_periods), 2)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta varios backtests consecutivos y los compara con DCA"
    )
    parser.add_argument(
        "--monthly",
        nargs="*",
        type=float,
        default=[],
        help="Aportes mensuales",
    )
    parser.add_argument(
        "--periods",
        nargs="*",
        help=(
            "Pares inicio fin para cada periodo. "
            "Si se omite se usan periodos por defecto"
        ),
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Ruta opcional para guardar CSV",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="Ruta opcional para guardar JSON",
    )
    args = parser.parse_args()

    periods = parse_periods(args.periods)

    params = {
        "rsi_oversold": 30,
        "bollinger_oversold": 0.08,
        "atr_multiplier": 3.0,
        "risk_per_trade": 0.005,
        "min_rsi": 30,
        "trend_filter": False,
    }

    rows = []
    for start, end in periods:
        rows.append(run_period(start, end, args.monthly, params))

    table = pd.DataFrame(rows)
    if not table.empty:
        print(table.to_string(index=False))
        if args.csv:
            csv_path = Path("results") / args.csv
            os.makedirs(csv_path.parent, exist_ok=True)
            table.to_csv(csv_path, index=False)
        if args.json:
            table.to_json(args.json, orient="records", indent=2)


if __name__ == "__main__":
    main()
