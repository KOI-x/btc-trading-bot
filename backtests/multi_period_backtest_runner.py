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
    start: str,
    end: str,
    deposits: List[float],
    params: Dict[str, Any],
    initial_usd: float,
) -> List[Dict[str, Any]]:
    """Execute the strategy and DCA baseline for a single period."""
    df_all = load_historical_data()
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    df = df_all[(df_all["Fecha"] >= start_dt) & (df_all["Fecha"] <= end_dt)]

    if df.empty:
        empty_row = {
            "periodo": f"{start} - {end}",
            "ciclo": "sin datos",
            "usd_invertido": 0.0,
            "btc_final": 0.0,
            "usd_final": 0.0,
            "retorno_btc_pct": 0.0,
            "retorno_usd_pct": 0.0,
            "señales_disparadas": 0,
            "fecha_ultima_compra": None,
        }
        base = empty_row.copy()
        base.update({"tipo": "estrategia"})
        dca = empty_row.copy()
        dca.update({"tipo": "dca"})
        resumen = empty_row.copy()
        resumen.update({"tipo": "resumen", "ventaja_pct_vs_dca": 0.0})
        return [base, dca, resumen]

    backtest = MonthlyInjectionBacktest(initial_usd=initial_usd)
    result = backtest.run(df, params, deposits)

    dca_btc = simple_dca(df, deposits, initial_usd)
    final_price = result["final_price"]
    dca_usd = dca_btc * final_price

    cycle = classify_cycle(df.iloc[0]["Precio USD"], final_price)
    invested = result["total_invested"]
    strat_row = {
        "periodo": f"{start} - {end}",
        "ciclo": cycle,
        "tipo": "estrategia",
        "usd_invertido": invested,
        "btc_final": result["btc_accumulated"],
        "usd_final": result["final_usd"],
        "retorno_btc_pct": result["btc_return"],
        "retorno_usd_pct": result["usd_return"],
        "señales_disparadas": result.get(
            "signals_triggered", len(result.get("trades", []))
        ),
        "fecha_ultima_compra": result.get("last_purchase"),
    }

    dca_ret_btc = (
        ((dca_btc / (invested / df.iloc[0]["Precio USD"])) - 1) * 100
        if invested > 0
        else 0
    )
    dca_ret_usd = ((dca_usd / invested) - 1) * 100 if invested > 0 else 0
    dca_row = {
        "periodo": f"{start} - {end}",
        "ciclo": cycle,
        "tipo": "dca",
        "usd_invertido": invested,
        "btc_final": dca_btc,
        "usd_final": dca_usd,
        "retorno_btc_pct": dca_ret_btc,
        "retorno_usd_pct": dca_ret_usd,
        "señales_disparadas": 0,
        "fecha_ultima_compra": df[df["Fecha"].dt.day == 1].iloc[-1]["Fecha"],
    }

    resumen = {
        "periodo": f"{start} - {end}",
        "ciclo": cycle,
        "tipo": "resumen",
        "usd_invertido": invested,
        "btc_final": result["btc_accumulated"],
        "usd_final": result["final_usd"],
        "retorno_btc_pct": result["btc_return"],
        "retorno_usd_pct": result["usd_return"],
        "ventaja_pct_vs_dca": (
            ((result["final_usd"] / dca_usd) - 1) * 100 if dca_usd > 0 else 0
        ),
        "señales_disparadas": strat_row["señales_disparadas"],
        "fecha_ultima_compra": strat_row["fecha_ultima_compra"],
    }

    return [strat_row, dca_row, resumen]


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
    parser.add_argument("--initial-usd", type=float, default=0.0)
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

    rows: List[Dict[str, Any]] = []
    for start, end in periods:
        rows.extend(run_period(start, end, args.monthly, params, args.initial_usd))

    table = pd.DataFrame(rows)
    if not table.empty:
        print(table.to_string(index=False))

        strat_rows = table[table["tipo"] == "estrategia"]
        dca_rows = table[table["tipo"] == "dca"]
        resumen_rows = table[table["tipo"] == "resumen"]

        mean_usd_strat = strat_rows["retorno_usd_pct"].mean()
        mean_usd_dca = dca_rows["retorno_usd_pct"].mean()
        mean_btc_strat = strat_rows["retorno_btc_pct"].mean()
        win_pct = (
            (resumen_rows["ventaja_pct_vs_dca"] > 0).sum() / len(resumen_rows) * 100
            if not resumen_rows.empty
            else 0
        )
        total_signals = int(strat_rows["señales_disparadas"].sum())

        print("\n--- Resumen global ---")
        print(f"Promedio retorno USD estrategia: {mean_usd_strat:.2f}%")
        print(f"Promedio retorno USD DCA: {mean_usd_dca:.2f}%")
        print(f"Promedio retorno BTC estrategia: {mean_btc_strat:.2f}%")
        print(f"Porcentaje de ciclos con ventaja: {win_pct:.1f}%")
        print(f"Total de señales disparadas: {total_signals}")

        if args.csv:
            csv_path = Path("results") / args.csv
            os.makedirs(csv_path.parent, exist_ok=True)
            table.to_csv(csv_path, index=False)
        if args.json:
            table.to_json(args.json, orient="records", indent=2)


if __name__ == "__main__":
    main()
