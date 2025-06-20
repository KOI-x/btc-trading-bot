"""Execute BTCAccumulationBacktest with monthly capital injections."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))  # noqa: E402

import argparse  # noqa: E402
from typing import Any, Dict, List  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from btc_accumulation_backtest import (  # noqa: E402
    BTCAccumulationBacktest,
    load_historical_data,
)


class MonthlyInjectionBacktest(BTCAccumulationBacktest):
    """Backtest que inyecta capital al inicio de cada mes."""

    def run(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any] | None = None,
        monthly_deposits: List[float] | None = None,
    ) -> Dict[str, Any]:
        """Execute the backtest injecting capital on the first day of each month."""

        self.reset()
        # Postpone initial capital deployment until the first monthly injection
        self.usd_balance = 0.0
        df = self.calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)
        deposits = monthly_deposits or []
        deposit_idx = 0

        for _, row in df.iterrows():
            if row["Fecha"].day == 1:
                if deposit_idx == 0 and self.initial_usd > 0:
                    self.usd_balance += self.initial_usd
                    self.total_invested += self.initial_usd
                if deposit_idx < len(deposits):
                    amt = deposits[deposit_idx]
                    self.usd_balance += amt
                    self.total_invested += amt
                deposit_idx += 1
            self.current_price = row["Precio USD"]
            should_buy, _ = self.get_buy_conditions(row, params or {})
            if should_buy and self.usd_balance > 10:
                position_size = self.calculate_position_size(
                    row["Precio USD"], row["ATR"], row["RSI"], row["Dist_Soporte"]
                )
                if position_size > 0:
                    self.execute_buy(row["Fecha"], row["Precio USD"], row["ATR"])
            total_equity = self.usd_balance + (self.btc_balance * row["Precio USD"])
            self.equity_curve.append(
                {
                    "date": row["Fecha"],
                    "usd_balance": self.usd_balance,
                    "btc_balance": self.btc_balance,
                    "btc_price": row["Precio USD"],
                    "total_equity": total_equity,
                    "btc_equity": self.btc_balance,
                }
            )
        final_price = df.iloc[-1]["Precio USD"]
        total_equity = self.usd_balance + (self.btc_balance * final_price)

        invested = self.total_invested
        if invested > 0:
            usd_return = ((total_equity / invested) - 1) * 100
            btc_return = (
                (self.btc_balance / (invested / df.iloc[0]["Precio USD"])) - 1
            ) * 100
        else:
            usd_return = 0
            btc_return = 0
        equity_curve = pd.DataFrame(self.equity_curve)
        equity_curve["peak"] = equity_curve["total_equity"].cummax()
        equity_curve["drawdown"] = (
            equity_curve["total_equity"] - equity_curve["peak"]
        ) / equity_curve["peak"]
        max_drawdown = equity_curve["drawdown"].min() * 100
        time_in_loss = (equity_curve["drawdown"] < 0).mean() * 100
        monthly_returns = (
            equity_curve.resample("M", on="date")["total_equity"]
            .last()
            .pct_change()
            .dropna()
        )
        sharpe_ratio = (
            (monthly_returns.mean() / monthly_returns.std()) * (12**0.5)
            if not monthly_returns.empty
            else 0.0
        )
        return {
            "initial_usd": self.initial_usd,
            "final_usd": total_equity,
            "btc_accumulated": self.btc_balance,
            "usd_return": usd_return,
            "btc_return": btc_return,
            "max_drawdown": abs(max_drawdown),
            "time_in_loss_pct": time_in_loss,
            "sharpe_ratio": sharpe_ratio,
            "trades": self.trades,
            "last_purchase": self.trades[-1]["date"] if self.trades else None,
            "signals_triggered": len(self.trades),
            "equity_curve": equity_curve,
            "final_price": final_price,
            "total_invested": invested,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest de acumulación con aportes mensuales"
    )
    parser.add_argument("--initial-usd", type=float, default=1000.0)
    parser.add_argument(
        "--monthly",
        type=float,
        nargs="*",
        default=[],
        help="Montos a aportar cada mes",
    )
    parser.add_argument("--start", type=str, default="2020-01-01")
    parser.add_argument("--end", type=str, default=None)
    args = parser.parse_args()
    df = load_historical_data()
    start = pd.to_datetime(args.start)
    end = pd.to_datetime(args.end) if args.end else pd.to_datetime("today")
    df = df[(df["Fecha"] >= start) & (df["Fecha"] <= end)]
    backtest = MonthlyInjectionBacktest(initial_usd=args.initial_usd)
    params = {
        "rsi_oversold": 30,
        "bollinger_oversold": 0.08,
        "atr_multiplier": 3.0,
        "risk_per_trade": 0.005,
        "min_rsi": 30,
        "trend_filter": False,
    }
    results = backtest.run(df, params, args.monthly)
    equity = pd.DataFrame(results["equity_curve"])
    print(equity.tail())
    print(f"BTC acumulado: {results['btc_accumulated']:.8f}")
    print(f"Valor final USD: ${results['final_usd']:.2f}")

    plt.figure(figsize=(14, 7))
    plt.subplot(2, 1, 1)
    plt.plot(
        equity["date"], equity["total_equity"], label="Valor Total (USD)", color="blue"
    )
    plt.title("Evolución del Valor Total (USD)")
    plt.grid(True)
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.plot(
        equity["date"], equity["btc_balance"], label="BTC Acumulados", color="orange"
    )
    plt.title("BTC Acumulados")
    plt.grid(True)
    plt.legend()

    os.makedirs("results", exist_ok=True)
    plt.tight_layout()
    plt.savefig("results/monthly_injection_result.png", dpi=300, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    main()
