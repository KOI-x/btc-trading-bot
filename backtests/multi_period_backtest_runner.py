from __future__ import annotations

"""Run monthly injection backtest over multiple periods and compare with DCA."""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd

# Add backtests directory to path so we can import sibling modules
sys.path.append(str(Path(__file__).parent))  # noqa: E402

from monthly_entry_comparison import classify_cycle, detect_environment  # noqa: E402
from monthly_injection_runner import (  # noqa: E402
    MonthlyInjectionBacktest,
    load_historical_data,
)


def dca_metrics(
    df: pd.DataFrame, deposits: List[float], initial_usd: float
) -> Tuple[float, float, float, float]:
    """Return final BTC and risk metrics for a DCA baseline."""

    btc_balance = 0.0
    deposit_idx = 0
    equity: List[Dict[str, Any]] = []
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
        total_equity = btc_balance * row["Precio USD"]
        equity.append({"date": row["Fecha"], "total_equity": total_equity})

    equity_df = pd.DataFrame(equity)
    equity_df["peak"] = equity_df["total_equity"].cummax()
    equity_df["drawdown"] = (equity_df["total_equity"] - equity_df["peak"]) / equity_df[
        "peak"
    ]
    max_drawdown = equity_df["drawdown"].min() * 100
    time_in_loss = (equity_df["drawdown"] < 0).mean() * 100
    monthly_returns = (
        equity_df.resample("M", on="date")["total_equity"].last().pct_change().dropna()
    )
    sharpe = (
        (monthly_returns.mean() / monthly_returns.std()) * (12**0.5)
        if not monthly_returns.empty
        else 0.0
    )
    return btc_balance, abs(max_drawdown), time_in_loss, sharpe


DEFAULT_PERIODS: List[Tuple[str, str]] = [
    ("2015-01-01", "2017-01-01"),
    ("2017-01-01", "2017-12-31"),
    ("2017-01-01", "2018-12-31"),
    ("2020-01-01", "2021-12-31"),
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

    dca_btc, dca_dd, dca_time_loss, dca_sharpe = dca_metrics(df, deposits, initial_usd)
    final_price = result["final_price"]
    dca_usd = dca_btc * final_price

    cycle = classify_cycle(df.iloc[0]["Precio USD"], final_price)
    env = detect_environment(df)
    invested = result["total_invested"]
    strat_row = {
        "periodo": f"{start} - {end}",
        "ciclo": cycle,
        "entorno": env,
        "tipo": "estrategia",
        "usd_invertido": invested,
        "btc_final": result["btc_accumulated"],
        "usd_final": result["final_usd"],
        "retorno_btc_pct": result["btc_return"],
        "retorno_usd_pct": result["usd_return"],
        "max_drawdown": result["max_drawdown"],
        "tiempo_en_perdida_pct": result["time_in_loss_pct"],
        "sharpe_ratio": result["sharpe_ratio"],
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
        "entorno": env,
        "tipo": "dca",
        "usd_invertido": invested,
        "btc_final": dca_btc,
        "usd_final": dca_usd,
        "retorno_btc_pct": dca_ret_btc,
        "retorno_usd_pct": dca_ret_usd,
        "max_drawdown": dca_dd,
        "tiempo_en_perdida_pct": dca_time_loss,
        "sharpe_ratio": dca_sharpe,
        "señales_disparadas": 0,
        "fecha_ultima_compra": df[df["Fecha"].dt.day == 1].iloc[-1]["Fecha"],
    }

    resumen = {
        "periodo": f"{start} - {end}",
        "ciclo": cycle,
        "entorno": env,
        "tipo": "resumen",
        "usd_invertido": invested,
        "btc_final": result["btc_accumulated"],
        "usd_final": result["final_usd"],
        "retorno_btc_pct": result["btc_return"],
        "retorno_usd_pct": result["usd_return"],
        "ventaja_pct_vs_dca": (
            ((result["final_usd"] / dca_usd) - 1) * 100 if dca_usd > 0 else 0
        ),
        "max_drawdown": result["max_drawdown"],
        "tiempo_en_perdida_pct": result["time_in_loss_pct"],
        "sharpe_ratio": result["sharpe_ratio"],
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


def sensitivity_analysis(
    periods: List[Tuple[str, str]],
    deposits: List[float],
    initial_usd: float,
    base_params: Dict[str, Any],
) -> pd.DataFrame:
    """Evaluate different parameter combinations."""

    results = []
    for rsi in [25, 30, 35]:
        for boll in [0.05, 0.08, 0.10]:
            params = base_params.copy()
            params["rsi_oversold"] = rsi
            params["bollinger_oversold"] = boll
            rows: List[Dict[str, Any]] = []
            for start, end in periods:
                rows.extend(run_period(start, end, deposits, params, initial_usd))
            df = pd.DataFrame(rows)
            resumen = df[df["tipo"] == "resumen"]
            results.append(
                {
                    "rsi": rsi,
                    "bollinger": boll,
                    "ventaja_vs_dca": resumen["ventaja_pct_vs_dca"].mean(),
                    "retorno_promedio": resumen["retorno_usd_pct"].mean(),
                }
            )
    table = pd.DataFrame(results)
    print("\n--- Sensibilidad parámetros ---")
    print(table.to_string(index=False))
    return table


def plot_comparison(table: pd.DataFrame, path: Path | None = None) -> None:
    """Save a bar plot comparing strategy vs DCA for each period."""

    pivot = table.pivot(index="periodo", columns="tipo", values="retorno_usd_pct")
    pivot = pivot.sort_index()
    pivot.plot(kind="bar", figsize=(10, 6))
    plt.ylabel("Retorno USD %")
    plt.title("Estrategia vs DCA por periodo")
    plt.grid(True, axis="y", linestyle=":")
    plt.tight_layout()
    if path is not None:
        os.makedirs(path.parent, exist_ok=True)
        plt.savefig(path, dpi=300, bbox_inches="tight")
    else:
        plt.show()
    plt.close()


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
        "--sensitivity", action="store_true", help="Analizar impacto de parametros"
    )
    parser.add_argument(
        "--plot", action="store_true", help="Mostrar grafico de retornos"
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

    rows: List[Dict[str, Any]] = []
    for start, end in periods:
        rows.extend(run_period(start, end, args.monthly, params, args.initial_usd))

    table = pd.DataFrame(rows)

    if args.sensitivity:
        sens_table = sensitivity_analysis(
            periods, args.monthly, args.initial_usd, params
        )
        if args.csv is None:
            timestamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
            args.csv = f"sensitivity_{timestamp}.csv"
        csv_path = Path("results") / args.csv
        os.makedirs(csv_path.parent, exist_ok=True)
        sens_table.to_csv(csv_path, index=False)

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

        bull_rows = resumen_rows[resumen_rows["entorno"] == "bull"]
        bull_adv = (
            bull_rows["ventaja_pct_vs_dca"].mean() if not bull_rows.empty else 0.0
        )

        print("\n--- Resumen global ---")
        print(f"Promedio retorno USD estrategia: {mean_usd_strat:.2f}%")
        print(f"Promedio retorno USD DCA: {mean_usd_dca:.2f}%")
        print(f"Promedio retorno BTC estrategia: {mean_btc_strat:.2f}%")
        print(f"Porcentaje de ciclos con ventaja: {win_pct:.1f}%")
        print(f"Total de señales disparadas: {total_signals}")
        print(f"Ventaja en entornos alcistas: {bull_adv:.2f}%")

        if args.csv:
            csv_path = Path("results") / args.csv
        else:
            timestamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
            csv_path = Path("results") / f"multi_period_{timestamp}.csv"
        os.makedirs(csv_path.parent, exist_ok=True)
        table.to_csv(csv_path, index=False)
        if args.json:
            table.to_json(args.json, orient="records", indent=2)

        if args.plot:
            plot_path = Path("results") / "multi_period_plot.png"
            plot_comparison(table, plot_path)


if __name__ == "__main__":
    main()
