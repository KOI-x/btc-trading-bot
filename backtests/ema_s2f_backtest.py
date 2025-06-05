import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import matplotlib.pyplot as plt
import argparse

from strategies.ema_s2f import evaluar_estrategia

EXCEL_FILE = Path("bitcoin_prices.xlsx")


def backtest(save_path: str | None = None):
    if not EXCEL_FILE.exists():
        print("No se encontró el archivo de precios.")
        return

    df = pd.read_excel(EXCEL_FILE)
    required_cols = {"Fecha", "Precio USD", "Desviación S2F %"}
    if not required_cols.issubset(df.columns):
        print("El archivo no contiene las columnas necesarias para el backtest.")
        return

    capital = 10000.0
    position = False
    entry_price = 0.0
    trades = 0
    wins = 0
    equity_curve = []

    for i in range(len(df)):
        sub_df = df.iloc[: i + 1]
        signal = evaluar_estrategia(sub_df)
        price = df.loc[i, "Precio USD"]

        if signal == "BUY" and not position:
            position = True
            entry_price = price
            trades += 1
        elif signal == "SELL" and position:
            if price > entry_price:
                wins += 1
            capital *= price / entry_price
            position = False

        equity = capital * (price / entry_price) if position else capital
        equity_curve.append(equity)

    if position:
        price = df.iloc[-1]["Precio USD"]
        if price > entry_price:
            wins += 1
        capital *= price / entry_price
        position = False
        equity_curve[-1] = capital

    win_rate = (wins / trades * 100) if trades else 0.0

    # Max drawdown
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdowns = (equity_series - running_max) / running_max
    max_drawdown = drawdowns.min() * 100

    print(f"Valor final de la cuenta: ${capital:.2f}")
    print(f"Cantidad de operaciones: {trades}")
    print(f"Win-rate: {win_rate:.2f}%")
    print(f"Max drawdown: {max_drawdown:.2f}%")

    plt.figure()
    plt.plot(df["Fecha"], equity_curve, label="Equity Curve")
    plt.xlabel("Fecha")
    plt.ylabel("Capital ($)")
    plt.title("Estrategia EMA S2F - Equity Curve")
    plt.legend()
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    else:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", dest="save", help="Ruta para guardar la curva de capital", required=False)
    args = parser.parse_args()
    backtest(args.save)
