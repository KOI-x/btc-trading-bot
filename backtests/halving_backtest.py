import os
import sys
from pathlib import Path

# Asegurarse de que el directorio raíz del proyecto esté en el path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.orm import sessionmaker

# Importaciones locales
from config import DATABASE_URL
from storage.database import get_price_history_df, init_db, init_engine
from strategies.halving_strategy import evaluar_estrategia, estimate_block_height

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PositionType(Enum):
    NONE = auto()
    LONG = auto()
    SHORT = auto()


def calculate_margin_requirements(leverage: float, position_size: float) -> float:
    """Calcula el margen requerido para una posición."""
    return position_size / leverage


def calculate_funding_cost(
    position_size: float, funding_rate: float, days: float
) -> float:
    """Calcula el costo de financiamiento para una posición."""
    return position_size * funding_rate * (days / 365)


def run_backtest(
    coin_id: str,
    initial_capital: float = 10000.0,
    start_date: str = "2012-01-01",  # Fecha inicial por defecto para cubrir varios ciclos
    leverage: float = 3.0,  # Menor apalancamiento por defecto para estrategia a largo plazo
    funding_rate: float = 0.01,
    stop_loss: float = 0.10,  # Stop loss más amplio para estrategia de largo plazo
    take_profit: float = 0.30,  # Take profit más amplio
) -> dict:
    """
    Ejecuta el backtest de la estrategia de halving y S2F.
    """
    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    logger.info("Obteniendo datos históricos...")
    with Session() as session:
        df = get_price_history_df(session, coin_id)

    # Asegurar que la columna de fechas sea datetime
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # Filtrar por fecha de inicio
    start_date = pd.to_datetime(start_date)
    df = df[df["Fecha"] >= start_date].reset_index(drop=True)

    if df.empty:
        logger.error("No hay datos disponibles para el rango de fechas especificado")
        return None

    # Inicializar variables de seguimiento
    capital = initial_capital
    position_type = PositionType.NONE
    entry_price = 0.0
    position_size = 0.0
    equity_curve = [capital]
    trades = []

    # Parámetros de la estrategia
    strategy_params = {
        "use_s2f": True,  # Habilitar modelo S2F
        "s2f_threshold": 0.3,  # Umbral de desviación del modelo S2F
        "max_leverage": leverage,  # Usar el apalancamiento especificado
        "risk_per_trade": 0.02,  # 2% de riesgo por operación
        "stop_loss": stop_loss,  # Stop loss del backtest
        "take_profit": take_profit,  # Take profit del backtest
        "capital": capital,  # Pasar el capital actual a la estrategia
    }

    # Bucle principal del backtest
    for i in range(1, len(df)):
        current_date = df["Fecha"].iloc[i]
        current_price = df["Precio USD"].iloc[i]

        # Actualizar parámetros dinámicos
        strategy_params["capital"] = capital
        strategy_params["block_height"] = estimate_block_height(current_date)

        # Obtener datos históricos hasta el día actual
        historical_data = df.iloc[: i + 1].copy()

        # Evaluar estrategia con todos los parámetros
        signal = evaluar_estrategia(historical_data, strategy_params)

        # Manejar posición abierta
        if position_type != PositionType.NONE:
            # Calcular PnL
            pnl_pct = (current_price - entry_price) / entry_price
            pnl_pct = pnl_pct * (-1 if position_type == PositionType.SHORT else 1)

            # Verificar stop loss/take profit dinámicos de la estrategia
            current_stop = strategy_params.get("current_stop_loss", stop_loss)
            current_take = strategy_params.get("current_take_profit", take_profit)

            if (pnl_pct <= -current_stop) or (pnl_pct >= current_take):
                # Cerrar posición
                pnl = position_size * pnl_pct
                capital += pnl

                trades.append(
                    {
                        "type": "CLOSE",
                        "date": current_date,
                        "price": current_price,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct * 100,
                        "position_type": (
                            "LONG" if position_type == PositionType.LONG else "SHORT"
                        ),
                        "capital": capital,
                        "reason": (
                            "SL/TP hit" if pnl_pct <= -current_stop else "Take Profit"
                        ),
                    }
                )

                position_type = PositionType.NONE
                position_size = 0.0
                entry_price = 0.0

        # Manejar señales de trading
        if signal == "BUY" and position_type == PositionType.NONE:
            # Abrir posición larga
            position_type = PositionType.LONG
            entry_price = current_price

            # Usar el tamaño de posición calculado por la estrategia o un valor por defecto
            position_size = capital * leverage

            # Registrar la operación
            trades.append(
                {
                    "type": "OPEN",
                    "date": current_date,
                    "price": current_price,
                    "position_type": "LONG",
                    "size": position_size,
                    "leverage": leverage,
                    "capital": capital,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                }
            )

        elif signal == "SELL" and position_type == PositionType.LONG:
            # Cerrar posición larga por señal de la estrategia
            pnl_pct = (current_price - entry_price) / entry_price
            pnl = position_size * pnl_pct
            capital += pnl

            trades.append(
                {
                    "type": "CLOSE",
                    "date": current_date,
                    "price": current_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct * 100,
                    "position_type": "LONG",
                    "capital": capital,
                    "reason": "Signal SELL",
                }
            )

            position_type = PositionType.NONE
            position_size = 0.0
            entry_price = 0.0

        # Actualizar curva de capital
        if position_type != PositionType.NONE:
            # Calcular valor actual de la posición
            position_value = position_size * (
                1 + (current_price - entry_price) / entry_price
            )
            equity = capital - position_size / leverage + position_value / leverage
        else:
            equity = capital

        equity_curve.append(equity)

    # Cerrar posición abierta al final si es necesario
    if position_type != PositionType.NONE:
        current_price = df["Precio USD"].iloc[-1]
        pnl_pct = (current_price - entry_price) / entry_price
        pnl = (
            position_size * pnl_pct * (1 if position_type == PositionType.LONG else -1)
        )
        capital += pnl

        trades.append(
            {
                "type": "CLOSE",
                "date": df["Fecha"].iloc[-1],
                "price": current_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct * 100,
                "position_type": (
                    "LONG" if position_type == PositionType.LONG else "SHORT"
                ),
                "capital": capital,
            }
        )

    # Calcular métricas
    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe_ratio = (
        (returns.mean() / returns.std()) * np.sqrt(252)
        if len(returns) > 1 and returns.std() > 0
        else 0
    )

    # Calcular CAGR
    years = (df["Fecha"].iloc[-1] - df["Fecha"].iloc[0]).days / 365.25
    cagr = (
        ((equity_curve[-1] / initial_capital) ** (1 / years) - 1) * 100
        if years > 0
        else 0
    )

    # Calcular drawdown
    peak = equity_curve[0]
    max_drawdown = 0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Calcular métricas de operaciones
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()

    if not trades_df.empty and "pnl" in trades_df.columns:
        winning_trades = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
        losing_trades = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
        total_trades = len(trades_df)
        winning_trades_count = len(trades_df[trades_df["pnl"] > 0])

        win_rate = (
            (winning_trades_count / total_trades * 100) if total_trades > 0 else 0
        )
        profit_factor = (
            winning_trades / losing_trades if losing_trades > 0 else float("inf")
        )
    else:
        total_trades = 0
        win_rate = 0
        profit_factor = 0

    return {
        "initial_capital": initial_capital,
        "final_capital": equity_curve[-1],
        "total_return_pct": (equity_curve[-1] / initial_capital - 1) * 100,
        "cagr_pct": cagr,
        "max_drawdown_pct": max_drawdown * 100,
        "sharpe_ratio": sharpe_ratio,
        "total_trades": total_trades,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "equity_curve": equity_curve,
        "trades": trades,
        "dates": df["Fecha"].tolist(),
        "prices": df["Precio USD"].tolist(),
    }


def plot_results(results: Dict[str, Any], save_path: str = None) -> None:
    """Grafica los resultados del backtest."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.gridspec import GridSpec

        # Configurar el estilo de los gráficos sin depender de estilos externos
        plt.style.use("default")
        plt.rcParams["figure.facecolor"] = "white"
        plt.rcParams["axes.facecolor"] = "white"
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.alpha"] = 0.3

        # Configurar la figura con un diseño personalizado
        fig = plt.figure(figsize=(14, 12))
        gs = GridSpec(3, 1, height_ratios=[2, 1, 1])

        # Obtener datos
        dates = results["dates"]
        equity_curve = results["equity_curve"]
        prices = results["prices"]
        trades = results.get("trades", [])

        # Normalizar para comparación
        initial_equity = equity_curve[0]
        initial_price = prices[0]

        norm_equity = [e / initial_equity for e in equity_curve]
        norm_hold = [p / initial_price for p in prices]

        # Calcular retornos
        strategy_return = (norm_equity[-1] - 1) * 100
        hold_return = (norm_hold[-1] - 1) * 100

        # Gráfico 1: Equity Curve vs Buy & Hold
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(
            dates,
            norm_equity,
            label=f"Estrategia Halving+S2F ({strategy_return:.1f}%)",
            linewidth=2,
            color="#1f77b4",
        )
        ax1.plot(
            dates,
            norm_hold,
            label=f"Comprar y Mantener ({hold_return:.1f}%)",
            linestyle="--",
            linewidth=1.5,
            color="#ff7f0e",
        )

        # Marcar operaciones
        for trade in trades:
            if trade["type"] == "OPEN":
                marker = "^" if trade["position_type"] == "LONG" else "v"
                color = "g" if trade["position_type"] == "LONG" else "r"
                ax1.scatter(
                    trade["date"],
                    norm_equity[dates.index(trade["date"])],
                    color=color,
                    marker=marker,
                    s=100,
                    zorder=5,
                    label=f"{'Compra' if trade['position_type'] == 'LONG' else 'Venta'}",
                )

        ax1.set_title(
            "Rendimiento: Estrategia Halving+S2F vs Comprar y Mantener",
            fontsize=14,
            pad=20,
        )
        ax1.set_ylabel("Retorno Normalizado", fontsize=12)
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)

        # Gráfico 2: Drawdown
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        peak = np.maximum.accumulate(norm_equity)
        drawdown = (peak - norm_equity) / peak
        ax2.fill_between(dates, 0, drawdown * 100, color="#d62728", alpha=0.3)
        ax2.set_ylabel("Drawdown (%)", fontsize=12)
        ax2.set_ylim(0, max(drawdown) * 110 if max(drawdown) > 0 else 10)
        ax2.grid(True, alpha=0.3)

        # Gráfico 3: Precio BTC
        ax3 = fig.add_subplot(gs[2], sharex=ax1)
        ax3.plot(dates, prices, label="Precio BTC", color="#2ca02c")
        ax3.set_ylabel("Precio (USD)", fontsize=12)
        ax3.grid(True, alpha=0.3)

        # Formatear ejes de fecha
        for ax in [ax1, ax2, ax3]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # Ajustar espaciado
        plt.tight_layout()
        plt.subplots_adjust(hspace=0.3)

        # Guardar o mostrar
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Gráfico guardado en: {save_path}")
        else:
            plt.show()

        # Cerrar la figura para liberar memoria
        plt.close(fig)

    except Exception as e:
        logger.error(f"Error al generar gráficos: {str(e)}")
        logger.debug("Detalles del error:", exc_info=True)


def backtest(
    save_path: str | None = None,
    coin_id: str = "bitcoin",
    start_date: str = "2012-01-01",
    leverage: float = 3.0,
    stop_loss: float = 0.10,
    take_profit: float = 0.30,
    funding_rate: float = 0.01,
) -> None:
    """Ejecuta el backtest y muestra los resultados."""
    print("\n" + "=" * 60)
    print(f"INICIANDO BACKTEST - Estrategia Halving+S2F ({leverage}x)".center(60))
    print("=" * 60)
    print(f"Moneda: {coin_id.upper()}")
    print(f"Período: {start_date} a {datetime.now().strftime('%Y-%m-%d')}")
    print(f"Stop Loss: {stop_loss*100}% | Take Profit: {take_profit*100}%")
    print(f"Apalancamiento: {leverage}x | Tasa de financiamiento: {funding_rate*100}%")
    print("-" * 60 + "\n")

    # Ejecutar backtest
    results = run_backtest(
        coin_id=coin_id,
        start_date=start_date,
        leverage=leverage,
        stop_loss=stop_loss,
        take_profit=take_profit,
        funding_rate=funding_rate,
    )

    if not results:
        print("Error al ejecutar el backtest.")
        return

    # Calcular métricas de holdear
    initial_price = results["prices"][0]
    final_price = results["prices"][-1]
    hold_return = (final_price - initial_price) / initial_price * 100

    # Calcular CAGR de holdear
    days = (results["dates"][-1] - results["dates"][0]).days
    hold_cagr = ((1 + hold_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0

    # Mostrar resultados
    print("\n" + "=" * 60)
    print("RESULTADOS DEL BACKTEST".center(60))
    print("=" * 60)
    print(
        f"Período: {results['dates'][0].strftime('%Y-%m-%d')} a {results['dates'][-1].strftime('%Y-%m-%d')}"
    )
    print(f"Días de trading: {days}")
    print(f"\n{'MÉTRICA':<25} {'ESTRATEGIA':<15} {'HOLDEAR':<15}")
    print("-" * 60)
    print(f"{'Capital Inicial:':<25} ${results['initial_capital']:,.2f}")
    print(
        f"{'Capital Final:':<25} ${results['final_capital']:,.2f} ${initial_price + (initial_price * hold_return/100):,.2f}"
    )
    print(
        f"{'Retorno Total (%):':<25} {results['total_return_pct']:>5.1f}% {hold_return:>14.1f}%"
    )
    print(f"{'CAGR (%):':<25} {results['cagr_pct']:>5.1f}% {hold_cagr:>14.1f}%")
    print(f"{'Máximo Drawdown (%):':<25} {results['max_drawdown_pct']:>5.1f}%")
    print(f"{'Operaciones:':<25} {results['total_trades']:>5}")
    print(f"{'Tasa de aciertos (%):':<25} {results['win_rate_pct']:>5.1f}%")
    print(f"{'Profit Factor:':<25} {results['profit_factor']:>5.2f}")
    print(f"{'Ratio de Sharpe:':<25} {results['sharpe_ratio']:>5.2f}")

    # Mostrar comparación de rendimiento
    print("\n" + "-" * 60)
    print("COMPARACIÓN DE RENDIMIENTO".center(60))
    print("-" * 60)
    strat_return = (results["final_capital"] / results["initial_capital"] - 1) * 100
    diff = strat_return - hold_return

    if diff > 0:
        print(f"La estrategia superó a holdear por {abs(diff):.1f}%")
    else:
        print(f"La estrategia quedó por debajo de holdear en {abs(diff):.1f}%")

    print("=" * 60 + "\n")

    # Mostrar resumen de operaciones
    if results["trades"]:
        print("\nÚLTIMAS 5 OPERACIONES:")
        print("-" * 60)
        print(f"{'Fecha':<12} {'Tipo':<6} {'Precio':<12} {'PnL %':<8} {'Capital'}")
        print("-" * 60)
        for trade in results["trades"][-5:]:
            if trade["type"] == "CLOSE":
                print(
                    f"{trade['date'].strftime('%Y-%m-%d')} {trade['position_type']:<6} "
                    f"${trade['price']:,.2f} {trade['pnl_pct']:>6.1f}%  "
                    f"${trade['capital']:,.2f}"
                )

    # Mostrar o guardar gráfico
    if save_path:
        plot_results(results, save_path)
    else:
        plot_results(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backtest de estrategia de Halving y S2F"
    )
    parser.add_argument(
        "--save", type=str, help="Ruta para guardar el gráfico de resultados"
    )
    parser.add_argument(
        "--coin", type=str, default="bitcoin", help="ID de la criptomoneda"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2012-01-01",
        help="Fecha de inicio (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--leverage", type=float, default=3.0, help="Nivel de apalancamiento"
    )
    parser.add_argument(
        "--stop-loss", type=float, default=0.10, help="Stop loss (ej: 0.10 para 10%)"
    )
    parser.add_argument(
        "--take-profit",
        type=float,
        default=0.30,
        help="Take profit (ej: 0.30 para 30%)",
    )
    parser.add_argument(
        "--funding-rate", type=float, default=0.01, help="Tasa de financiamiento anual"
    )

    args = parser.parse_args()

    backtest(
        save_path=args.save,
        coin_id=args.coin,
        start_date=args.start_date,
        leverage=args.leverage,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
        funding_rate=args.funding_rate,
    )
