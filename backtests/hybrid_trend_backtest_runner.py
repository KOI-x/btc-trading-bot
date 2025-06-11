from __future__ import annotations

"""Run an adaptive DCA strategy filtered by SMA200."""

import argparse
import os

# Add backtests directory to path so we can import sibling modules
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

sys.path.append(str(Path(__file__).parent))  # noqa: E402

from monthly_entry_comparison import detect_environment  # noqa: E402
from monthly_injection_runner import (  # noqa: E402
    MonthlyInjectionBacktest,
    load_historical_data,
)


class HybridTrendBacktest:
    """Adaptive monthly accumulation using SMA200 filter."""

    def __init__(
        self,
        initial_usd: float,
        base_monthly: float,
        adjust_factor: float,
        rsi_threshold: float,
        bear_monthly: float,
        neutral_monthly: float,
    ) -> None:
        self.initial_usd = initial_usd
        self.base = base_monthly
        self.factor = adjust_factor
        self.rsi_thr = rsi_threshold
        self.bear_monthly = bear_monthly
        self.neutral_monthly = neutral_monthly

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        bt = MonthlyInjectionBacktest(initial_usd=self.initial_usd)
        df = bt.calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)

        btc_balance = 0.0
        total_invested = 0.0
        last_month = None

        for _, row in df.iterrows():
            date = row["Fecha"]
            price = row["Precio USD"]
            if last_month is None or date.month != last_month:
                last_month = date.month
                sma50 = row["SMA_50"]
                sma200 = row["SMA_200"]
                rsi = row["RSI"]
                if price > sma200:  # Bullish environment
                    amount = self.base + (price / sma50 - 1) * self.factor
                    if rsi < self.rsi_thr and amount > 0:
                        btc_balance += amount / price
                        total_invested += amount
                elif price < sma200:  # Bearish
                    if self.bear_monthly > 0:
                        btc_balance += self.bear_monthly / price
                        total_invested += self.bear_monthly
                else:  # Neutral
                    if self.neutral_monthly > 0:
                        btc_balance += self.neutral_monthly / price
                        total_invested += self.neutral_monthly

        final_price = df.iloc[-1]["Precio USD"]
        final_usd = btc_balance * final_price
        return {
            "btc_final": btc_balance,
            "usd_final": final_usd,
            "usd_invertido": total_invested,
        }


def simple_dca(df: pd.DataFrame, monthly: float, initial_usd: float) -> float:
    """Buy fixed USD amount on the first day of each month."""
    btc_balance = 0.0
    first = True
    for _, row in df.iterrows():
        if row["Fecha"].day == 1:
            amt = initial_usd if first else 0.0
            amt += monthly
            first = False
            if amt > 0:
                btc_balance += amt / row["Precio USD"]
    return btc_balance


def run_period(
    start: str,
    end: str,
    params: Dict[str, Any],
    args: argparse.Namespace,
) -> List[Dict[str, Any]]:
    df_all = load_historical_data()
    df = df_all[
        (df_all["Fecha"] >= pd.to_datetime(start))
        & (df_all["Fecha"] <= pd.to_datetime(end))
    ]
    if df.empty:
        raise ValueError("No hay datos para el periodo especificado")

    env = detect_environment(df)

    # Baseline strategy with constant deposits
    months = len(df[df["Fecha"].dt.day == 1])
    monthly_deposits = [args.base_monthly] * months
    base_bt = MonthlyInjectionBacktest(initial_usd=args.initial_usd)
    base_res = base_bt.run(df, params, monthly_deposits)

    # Pure DCA
    dca_btc = simple_dca(df, args.base_monthly, args.initial_usd)
    dca_usd = dca_btc * df.iloc[-1]["Precio USD"]

    # Adaptive strategy
    hybrid_bt = HybridTrendBacktest(
        initial_usd=args.initial_usd,
        base_monthly=args.base_monthly,
        adjust_factor=args.factor,
        rsi_threshold=args.rsi_threshold,
        bear_monthly=args.bear_monthly,
        neutral_monthly=args.neutral_monthly,
    )
    hybrid_res = hybrid_bt.run(df)

    ventaja_hybrid = (
        ((hybrid_res["usd_final"] / dca_usd) - 1) * 100 if dca_usd > 0 else 0
    )
    ventaja_base = ((base_res["final_usd"] / dca_usd) - 1) * 100 if dca_usd > 0 else 0

    rows = [
        {
            "periodo": f"{start} - {end}",
            "entorno": env,
            "tendencia_activa": env == "bull",
            "modo_estrategia": "compra_adaptativa",
            "usd_invertido": hybrid_res["usd_invertido"],
            "btc_final": hybrid_res["btc_final"],
            "usd_final": hybrid_res["usd_final"],
            "ventaja_pct_vs_dca": ventaja_hybrid,
        },
        {
            "periodo": f"{start} - {end}",
            "entorno": env,
            "tendencia_activa": env == "bull",
            "modo_estrategia": "estrategia_base",
            "usd_invertido": base_res["total_invested"],
            "btc_final": base_res["btc_accumulated"],
            "usd_final": base_res["final_usd"],
            "ventaja_pct_vs_dca": ventaja_base,
        },
        {
            "periodo": f"{start} - {end}",
            "entorno": env,
            "tendencia_activa": env == "bull",
            "modo_estrategia": "dca_fijo",
            "usd_invertido": args.base_monthly * months + args.initial_usd,
            "btc_final": dca_btc,
            "usd_final": dca_usd,
            "ventaja_pct_vs_dca": 0.0,
        },
    ]
    return rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backtest adaptativo basado en SMA200 y RSI"
    )
    p.add_argument("--start", type=str, default="2019-01-01")
    p.add_argument("--end", type=str, default="2024-01-01")
    p.add_argument("--initial-usd", type=float, default=0.0)
    p.add_argument("--base-monthly", type=float, default=100.0)
    p.add_argument("--factor", type=float, default=100.0)
    p.add_argument("--rsi-threshold", type=float, default=45.0)
    p.add_argument("--bear-monthly", type=float, default=0.0)
    p.add_argument("--neutral-monthly", type=float, default=0.0)
    p.add_argument("--csv", type=str, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    params = {
        "rsi_oversold": 30,
        "bollinger_oversold": 0.08,
        "atr_multiplier": 3.0,
        "risk_per_trade": 0.005,
        "min_rsi": 30,
        "trend_filter": False,
    }
    rows = run_period(args.start, args.end, params, args)
    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    if args.csv:
        out = Path("results") / args.csv
    else:
        timestamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
        out = Path("results") / f"hybrid_{timestamp}.csv"
    os.makedirs(out.parent, exist_ok=True)
    table.to_csv(out, index=False)


if __name__ == "__main__":
    main()
