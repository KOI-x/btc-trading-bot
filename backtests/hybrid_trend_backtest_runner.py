from __future__ import annotations

"""Hybrid accumulation backtest with market environment detection."""

import argparse
import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def compute_rsi(series: pd.Series, period: int) -> pd.Series:
    """Return RSI for the given period."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - 100 / (1 + rs)
    return rsi


def load_historical_data(
    file_path: str = "fixtures/price_history/BTC_USD.csv",
) -> pd.DataFrame:
    """Load price history and compute indicators."""
    df = pd.read_csv(file_path)
    df = df.rename(columns={"date": "Fecha", "price": "Precio USD"})
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df = df.sort_values("Fecha").reset_index(drop=True)
    df["SMA50"] = df["Precio USD"].rolling(50).mean()
    df["SMA200"] = df["Precio USD"].rolling(200).mean()
    df["RSI_45"] = compute_rsi(df["Precio USD"], 45)
    return df


def detect_environment(df: pd.DataFrame, threshold: float = 0.05) -> str:
    """Classify market as bull, bear or neutral based on SMA200."""
    price = df["Precio USD"].iloc[-1]
    sma = df["SMA200"].iloc[-1]
    if price > sma * (1 + threshold):
        return "bull"
    if price < sma * (1 - threshold):
        return "bear"
    return "neutral"


def run_strategy(
    df: pd.DataFrame,
    base: float,
    factor: float,
    fixed: float,
    rsi_thr: float,
    env_thr: float,
) -> Dict[str, Any]:
    """Execute adaptive monthly purchases based on market environment."""
    btc_balance = 0.0
    usd_invested = 0.0
    equity = []

    for i, row in df.iterrows():
        if i < 200:
            continue
        if row["Fecha"].day == 1:
            history = df.iloc[: i + 1]
            env = detect_environment(history, env_thr)
            sma50 = history["SMA50"].iloc[-1]
            rsi45 = history["RSI_45"].iloc[-1]
            if env == "bull":
                adaptive = base + (row["Precio USD"] / sma50 - 1) * factor
                amount = adaptive if rsi45 >= rsi_thr else base
            else:
                amount = fixed
            if amount > 0:
                btc_balance += amount / row["Precio USD"]
                usd_invested += amount
        equity.append({"date": row["Fecha"], "equity": btc_balance * row["Precio USD"]})

    final_env = detect_environment(df, env_thr)
    trend = "alcista" if df["SMA50"].iloc[-1] > df["SMA200"].iloc[-1] else "bajista"
    final_price = df.iloc[-1]["Precio USD"]
    final_usd = btc_balance * final_price
    usd_return = ((final_usd / usd_invested) - 1) * 100 if usd_invested > 0 else 0.0
    equity_df = pd.DataFrame(equity)
    equity_df["peak"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df[
        "peak"
    ]
    max_dd = equity_df["drawdown"].min() * 100 if not equity_df.empty else 0.0
    monthly_returns = (
        equity_df.resample("M", on="date")["equity"].last().pct_change().dropna()
    )
    sharpe = (
        (monthly_returns.mean() / monthly_returns.std()) * (12**0.5)
        if not monthly_returns.empty
        else 0.0
    )
    return {
        "entorno": final_env,
        "tendencia": trend,
        "btc_final": btc_balance,
        "usd_final": final_usd,
        "usd_return_pct": usd_return,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "total_invested": usd_invested,
    }


def run_dca(df: pd.DataFrame, base: float) -> Dict[str, Any]:
    """Simulate fixed monthly purchases."""
    btc_balance = 0.0
    equity = []
    for _, row in df.iterrows():
        if row["Fecha"].day == 1:
            btc_balance += base / row["Precio USD"]
        equity.append({"date": row["Fecha"], "equity": btc_balance * row["Precio USD"]})
    invested = len(df[df["Fecha"].dt.day == 1]) * base
    final_price = df.iloc[-1]["Precio USD"]
    final_usd = btc_balance * final_price
    usd_return = ((final_usd / invested) - 1) * 100 if invested > 0 else 0.0
    equity_df = pd.DataFrame(equity)
    equity_df["peak"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df[
        "peak"
    ]
    max_dd = equity_df["drawdown"].min() * 100 if not equity_df.empty else 0.0
    monthly_returns = (
        equity_df.resample("M", on="date")["equity"].last().pct_change().dropna()
    )
    sharpe = (
        (monthly_returns.mean() / monthly_returns.std()) * (12**0.5)
        if not monthly_returns.empty
        else 0.0
    )
    return {
        "btc_final": btc_balance,
        "usd_final": final_usd,
        "usd_return_pct": usd_return,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "total_invested": invested,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest híbrido con detección de entornos de mercado"
    )
    parser.add_argument("--base", type=float, default=100.0, help="Aporte base mensual")
    parser.add_argument(
        "--factor",
        type=float,
        default=200.0,
        help="Factor de ajuste para la compra adaptativa",
    )
    parser.add_argument(
        "--fixed", type=float, default=50.0, help="Aporte en mercados neutro o bajista"
    )
    parser.add_argument(
        "--rsi-threshold",
        type=float,
        default=55.0,
        help="Umbral de RSI(45) para habilitar la compra adaptativa",
    )
    parser.add_argument(
        "--env-threshold",
        type=float,
        default=0.05,
        help="Margen para clasificar bull/bear respecto a la SMA200",
    )
    parser.add_argument("--start-date", type=str, default="2015-01-01")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument(
        "--csv", type=str, default=None, help="Nombre opcional para guardar CSV"
    )
    args = parser.parse_args()

    df = load_historical_data()
    start = pd.to_datetime(args.start_date)
    end = pd.to_datetime(args.end_date) if args.end_date else pd.to_datetime("today")
    df = df[(df["Fecha"] >= start) & (df["Fecha"] <= end)]
    df = df.dropna().reset_index(drop=True)

    strat = run_strategy(
        df, args.base, args.factor, args.fixed, args.rsi_threshold, args.env_threshold
    )
    dca = run_dca(df, args.base)

    rows = [
        {
            "entorno": strat["entorno"],
            "tendencia": strat["tendencia"],
            "modo_estrategia": "adaptativa",
            "btc_final": strat["btc_final"],
            "usd_final": strat["usd_final"],
            "retorno_usd_pct": strat["usd_return_pct"],
            "max_drawdown": strat["max_drawdown"],
            "sharpe_ratio": strat["sharpe_ratio"],
        },
        {
            "entorno": strat["entorno"],
            "tendencia": strat["tendencia"],
            "modo_estrategia": "dca",
            "btc_final": dca["btc_final"],
            "usd_final": dca["usd_final"],
            "retorno_usd_pct": dca["usd_return_pct"],
            "max_drawdown": dca["max_drawdown"],
            "sharpe_ratio": dca["sharpe_ratio"],
        },
    ]

    results = pd.DataFrame(rows)
    os.makedirs("results", exist_ok=True)
    csv_name = (
        args.csv
        or f"hybrid_trend_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    csv_path = Path("results") / csv_name
    results.to_csv(csv_path, index=False)
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
