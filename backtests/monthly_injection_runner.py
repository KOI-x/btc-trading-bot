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
        self.reset()
        df = self.calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)
        deposits = monthly_deposits or []
        current_month = df.iloc[0]["Fecha"].month
        deposit_idx = 0
        if deposits:
            self.usd_balance += deposits[0]
            self.total_invested += deposits[0]
        for _, row in df.iterrows():
            month = row["Fecha"].month
            if month != current_month:
                current_month = month
                deposit_idx += 1
                if deposit_idx < len(deposits):
                    amt = deposits[deposit_idx]
                    self.usd_balance += amt
                    self.total_invested += amt
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
        usd_return = ((total_equity / self.initial_usd) - 1) * 100
        btc_start = self.initial_usd / df.iloc[0]["Precio USD"]
        btc_return = ((self.btc_balance / btc_start) - 1) * 100
        equity_curve = pd.DataFrame(self.equity_curve)
        equity_curve["peak"] = equity_curve["total_equity"].cummax()
        equity_curve["drawdown"] = (
            equity_curve["total_equity"] - equity_curve["peak"]
        ) / equity_curve["peak"]
        max_drawdown = equity_curve["drawdown"].min() * 100
        return {
            "initial_usd": self.initial_usd,
            "final_usd": total_equity,
            "btc_accumulated": self.btc_balance,
            "usd_return": usd_return,
            "btc_return": btc_return,
            "max_drawdown": abs(max_drawdown),
            "trades": self.trades,
            "equity_curve": equity_curve,
            "final_price": final_price,
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

    if not equity.empty:
        plt.figure(figsize=(14, 7))
        plt.subplot(2, 1, 1)
        plt.plot(equity["date"], equity["total_equity"], label="Valor Total (USD)")
        plt.title("Evolución del Valor Total (USD)")
        plt.grid(True)
        plt.legend()

        plt.subplot(2, 1, 2)
        plt.plot(
            equity["date"],
            equity["btc_balance"],
            label="BTC Acumulados",
            color="orange",
        )
        plt.title("BTC Acumulados")
        plt.grid(True)
        plt.legend()

        os.makedirs("results", exist_ok=True)
        output_file = Path("results") / "monthly_injection_result.png"
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        plt.close()


if __name__ == "__main__":
    main()
