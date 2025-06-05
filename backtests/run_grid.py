"""Ejecuta una búsqueda de parámetros para estrategias."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # noqa: E402

import importlib  # noqa: E402
import itertools  # noqa: E402

import pandas as pd  # noqa: E402

from tools.ensure_data_and_run import ensure_data  # noqa: E402

EXCEL_FILE = Path("bitcoin_prices.xlsx")


def load_data() -> pd.DataFrame:
    if not EXCEL_FILE.exists():
        raise FileNotFoundError("No se encontró el archivo de precios")
    return pd.read_excel(EXCEL_FILE)


def run_backtest(module_name: str, **params) -> tuple[float, float]:
    module = importlib.import_module(module_name)
    strategy = getattr(module, "evaluar_estrategia")

    df = load_data()
    capital = 10000.0
    position = False
    entry_price = 0.0
    equity_curve = []

    for i in range(len(df)):
        sub_df = df.iloc[: i + 1]
        signal = strategy(sub_df, **params)
        price = df.loc[i, "Precio USD"]

        if signal == "BUY" and not position:
            position = True
            entry_price = price
        elif signal == "SELL" and position:
            capital *= price / entry_price
            position = False

        equity = capital * (price / entry_price) if position else capital
        equity_curve.append(equity)

    if position:
        price = df.iloc[-1]["Precio USD"]
        capital *= price / entry_price
        equity_curve[-1] = capital

    equity_series = pd.Series(equity_curve)
    returns = equity_series.pct_change().dropna()
    annual_factor = 252**0.5
    # fmt: off
    sharpe = (returns.mean() / returns.std()) * annual_factor if not returns.empty else 0.0  # noqa: E501
    # fmt: on
    return capital, sharpe


def main():
    ensure_data()
    grid = {
        "strategies.rsi_mean_reversion": {
            "rsi_period": [14, 21],
            "overbought": [70],
            "oversold": [30],
        },
        "strategies.s2f_only": {
            "threshold_buy": [-25, -20],
            "threshold_sell": [20, 25],
        },
    }

    results = []
    for module_name, param_grid in grid.items():
        keys, values = zip(*param_grid.items())
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            final_capital, sharpe = run_backtest(module_name, **params)
            results.append(
                {
                    "strategy": module_name,
                    **params,
                    "capital": final_capital,
                    "sharpe": sharpe,
                }
            )

    df = pd.DataFrame(results)
    print(df.sort_values(by="sharpe", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
