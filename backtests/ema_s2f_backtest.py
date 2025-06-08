import argparse
from math import sqrt

import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from storage.database import get_price_history_df, init_db, init_engine
from strategies.ema_s2f import evaluar_estrategia


def run_backtest(
    coin_id: str, initial_capital: float = 10000.0, start_date: str | None = None
) -> dict:
    """Run the EMA S2F strategy and return key metrics."""

    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        df = get_price_history_df(session, coin_id)
    if start_date is not None:
        df = df[df["Fecha"] >= start_date].reset_index(drop=True)
    required_cols = {"Fecha", "Precio USD", "Desviación S2F %"}
    if not required_cols.issubset(df.columns):
        msg = "Datos insuficientes para el backtest"
        raise ValueError(msg)

    capital = float(initial_capital)
    position = False
    entry_price = 0.0
    equity_curve: list[float] = []

    for i in range(len(df)):
        sub_df = df.iloc[: i + 1]
        signal = evaluar_estrategia(sub_df)
        price = df.loc[i, "Precio USD"]

        if signal == "BUY" and not position:
            position = True
            entry_price = price
        elif signal == "SELL" and position:
            capital *= price / entry_price
            position = False

        equity = capital * (price / entry_price) if position else capital
        equity_curve.append(float(equity))

    if position:
        price = df.iloc[-1]["Precio USD"]
        capital *= price / entry_price
        equity_curve[-1] = float(capital)

    equity_series = pd.Series(equity_curve)
    start = pd.to_datetime(df["Fecha"].iloc[0])
    end = pd.to_datetime(df["Fecha"].iloc[-1])
    days = (end - start).days
    cagr = (capital / initial_capital) ** (365 / days) - 1 if days else 0.0
    returns = equity_series.pct_change().dropna()
    if returns.empty:
        sharpe = 0.0
    else:
        sharpe = (returns.mean() / returns.std()) * sqrt(365)

    return {
        "total_return": capital / initial_capital - 1,
        "cagr": cagr,
        "sharpe": sharpe,
        "equity_curve": equity_curve,
    }


def backtest(save_path: str | None = None, coin_id: str = "bitcoin"):
    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        df = get_price_history_df(session, coin_id)
    required_cols = {"Fecha", "Precio USD", "Desviación S2F %"}
    if not required_cols.issubset(df.columns):
        print("No se encontraron datos suficientes para el backtest.")
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

    # CAGR y Sharpe Ratio
    days = (
        pd.to_datetime(df["Fecha"].iloc[-1]) - pd.to_datetime(df["Fecha"].iloc[0])
    ).days
    if days == 0:
        cagr = 0.0
    else:
        cagr = (capital / 10000.0) ** (365 / days) - 1

    returns = equity_series.pct_change().dropna()
    if returns.empty:
        sharpe = 0.0
    else:
        sharpe = (returns.mean() / returns.std()) * sqrt(365)

    print(f"Valor final de la cuenta: ${capital:.2f}")
    print(f"Cantidad de operaciones: {trades}")
    print(f"Win-rate: {win_rate:.2f}%")
    print(f"Max drawdown: {max_drawdown:.2f}%")
    print(f"CAGR: {cagr * 100:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")

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
    parser.add_argument(
        "--save",
        dest="save",
        help="Ruta para guardar la curva de capital",
        required=False,
    )
    parser.add_argument(
        "--coin-id",
        dest="coin_id",
        default="bitcoin",
        help="Activo sobre el que ejecutar el backtest",
    )
    args = parser.parse_args()
    backtest(args.save, coin_id=args.coin_id)
