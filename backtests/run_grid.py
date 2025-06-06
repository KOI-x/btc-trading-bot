"""Ejecuta una búsqueda de parámetros para estrategias."""

import importlib
import itertools

import pandas as pd

from storage.models import get_price_history_df
from tools.ensure_data_and_run import ensure_data


def load_data(coin_id: str) -> pd.DataFrame:
    return get_price_history_df(coin_id)


def run_backtest(module_name: str, coin_id: str, **params) -> tuple[float, float]:
    module = importlib.import_module(module_name)
    strategy = getattr(module, "evaluar_estrategia")

    df = load_data(coin_id)
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
    sharpe = (returns.mean() / returns.std()) * (252**0.5) if not returns.empty else 0.0
    return capital, sharpe


def main(coin_id: str) -> None:
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
            final_capital, sharpe = run_backtest(module_name, coin_id, **params)
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
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coin-id",
        dest="coin_id",
        default="bitcoin",
        help="Activo sobre el que ejecutar el backtest",
    )
    args = parser.parse_args()
    main(args.coin_id)
