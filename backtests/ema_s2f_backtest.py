import argparse
import logging
from enum import Enum, auto
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from storage.database import get_price_history_df, init_db, init_engine
from strategies.ema_s2f import evaluar_estrategia

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
    start_date: str | None = None,
    leverage: float = 5.0,  # 5x apalancamiento por defecto
    funding_rate: float = 0.01,  # 1% de tasa de financiamiento anual
    stop_loss: float = 0.05,  # 5% de stop loss
    take_profit: float = 0.10,  # 10% de take profit
) -> dict:
    """Ejecuta la estrategia EMA con margen y devuelve métricas clave."""
    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    logger.info("Obteniendo datos históricos...")
    with Session() as session:
        df = get_price_history_df(session, coin_id)

    if start_date is not None:
        df = df[df["Fecha"] >= start_date].reset_index(drop=True)

    required_cols = {"Fecha", "Precio USD"}
    if not required_cols.issubset(df.columns):
        msg = "Datos insuficientes para el backtest"
        raise ValueError(msg)

    # Ordenar por fecha
    df = df.sort_values("Fecha").reset_index(drop=True)

    # Mostrar información sobre los datos
    logger.info(f"Total de registros cargados: {len(df)}")
    logger.info(f"Período: {df['Fecha'].iloc[0]} al {df['Fecha'].iloc[-1]}")

    # Inicializar variables de seguimiento
    capital = float(initial_capital)
    position_type = PositionType.NONE
    position_size = 0.0
    entry_price = 0.0
    equity_curve: List[float] = [capital]
    trades = 0
    winning_trades = 0
    losing_trades = 0
    total_pnl = 0.0
    max_drawdown = 0.0
    peak_equity = capital

    # Tamaño mínimo de la ventana para comenzar el backtest
    min_window_size = 50

    logger.info("Ejecutando backtest...")

    for i in range(min_window_size, len(df)):
        current_data = df.iloc[: i + 1].copy()
        current_price = current_data["Precio USD"].iloc[-1]

        # Calcular señales
        signal = evaluar_estrategia(current_data)

        # Calcular PnL de la posición actual
        if position_type == PositionType.LONG:
            pnl = (current_price - entry_price) * position_size
            current_equity = capital + pnl

            # Verificar stop loss y take profit para posición larga
            price_change = (current_price - entry_price) / entry_price
            if price_change <= -stop_loss or price_change >= take_profit:
                capital += pnl
                trades += 1
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
                total_pnl += pnl
                position_type = PositionType.NONE
                position_size = 0.0
                logger.info(
                    f"Cerrar LARGO - Precio: {current_price:.2f} - PnL: {pnl:.2f}"
                )

        elif position_type == PositionType.SHORT:
            pnl = (entry_price - current_price) * position_size
            current_equity = capital + pnl

            # Verificar stop loss y take profit para posición corta
            price_change = (entry_price - current_price) / entry_price
            if price_change <= -stop_loss or price_change >= take_profit:
                capital += pnl
                trades += 1
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
                total_pnl += pnl
                position_type = PositionType.NONE
                position_size = 0.0
                logger.info(
                    f"Cerrar CORTO - Precio: {current_price:.2f} - PnL: {pnl:.2f}"
                )
        else:
            current_equity = capital

        # Actualizar drawdown
        if current_equity > peak_equity:
            peak_equity = current_equity
        drawdown = (peak_equity - current_equity) / peak_equity
        max_drawdown = max(max_drawdown, drawdown)

        equity_curve.append(current_equity)

        # Ejecutar órdenes solo si no hay posición abierta
        if position_type == PositionType.NONE:
            if signal == "BUY":
                # Abrir posición larga
                position_type = PositionType.LONG
                position_size = (capital * leverage) / current_price
                entry_price = current_price
                logger.info(
                    "Abrir LARGO - Precio: %.2f - Tamaño: %.6f BTC",
                    current_price,
                    position_size,
                )

            elif signal == "SELL":
                # Abrir posición corta
                position_type = PositionType.SHORT
                position_size = (capital * leverage) / current_price
                entry_price = current_price
                logger.info(
                    "Abrir CORTO - Precio: %.2f - Tamaño: %.6f BTC",
                    current_price,
                    position_size,
                )

    # Cerrar cualquier posición abierta al final del backtest
    if position_type != PositionType.NONE:
        if position_type == PositionType.LONG:
            pnl = (df["Precio USD"].iloc[-1] - entry_price) * position_size
        else:  # SHORT
            pnl = (entry_price - df["Precio USD"].iloc[-1]) * position_size

        capital += pnl
        total_pnl += pnl
        trades += 1
        if pnl > 0:
            winning_trades += 1
        else:
            losing_trades += 1

    # Calcular métricas finales
    total_return = (capital / initial_capital - 1) * 100
    days = (df["Fecha"].iloc[-1] - df["Fecha"].iloc[0]).days or 1
    cagr = (capital / initial_capital) ** (365.25 / days) - 1
    cagr_pct = cagr * 100

    # Calcular ratio de Sharpe (asumiendo tasa libre de riesgo del 0% para simplificar)
    returns = pd.Series(equity_curve).pct_change().dropna()
    sharpe_ratio = (
        (returns.mean() / returns.std()) * (252**0.5) if len(returns) > 1 else 0
    )

    win_rate = (winning_trades / trades * 100) if trades > 0 else 0

    return {
        "initial_capital": initial_capital,
        "final_capital": capital,
        "total_return_pct": total_return,
        "cagr_pct": cagr_pct,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_drawdown * 100,
        "total_trades": trades,
        "win_rate_pct": win_rate,
        "profit_factor": (
            (winning_trades / losing_trades) if losing_trades > 0 else float("inf")
        ),
        "equity_curve": equity_curve,
        "dates": df["Fecha"].tolist(),
        "prices": df["Precio USD"].tolist(),
    }


def plot_results(results: Dict[str, Any], save_path: str = None) -> None:
    """Grafica los resultados del backtest incluyendo comparación con holdear."""
    import matplotlib.pyplot as plt

    # Configurar el gráfico
    plt.figure(figsize=(14, 8))

    # Obtener datos
    dates = results["dates"]
    equity_curve = results["equity_curve"]
    prices = results["prices"]

    # Normalizar ambas curvas para comparación
    initial_equity = equity_curve[0]
    initial_price = prices[0]

    norm_equity = [e / initial_equity for e in equity_curve]
    norm_hold = [p / initial_price for p in prices]

    # Asegurar que las fechas y las curvas tengan la misma longitud
    min_len = min(len(dates), len(norm_equity), len(norm_hold))
    dates = dates[:min_len]
    norm_equity = norm_equity[:min_len]
    norm_hold = norm_hold[:min_len]

    # Calcular retornos
    strategy_return = (norm_equity[-1] - 1) * 100
    hold_return = (norm_hold[-1] - 1) * 100

    # Crear gráfico
    plt.plot(
        dates,
        norm_equity,
        label=f"Estrategia EMA+RSI Trend ({strategy_return:.1f}%)",
        linewidth=2.5,
    )
    plt.plot(
        dates,
        norm_hold,
        label=f"Comprar y Mantener ({hold_return:.1f}%)",
        linestyle="--",
        linewidth=2,
    )

    # Añadir líneas verticales para operaciones
    trades = results.get("trades", [])
    for trade in trades:
        if trade["type"] == "BUY":
            plt.axvline(x=trade["date"], color="g", linestyle=":", alpha=0.3)
        elif trade["type"] == "SELL":
            plt.axvline(x=trade["date"], color="r", linestyle=":", alpha=0.3)

    # Configuración del gráfico
    plt.title("Comparación: Estrategia vs Comprar y Mantener")
    plt.xlabel("Fecha")
    plt.ylabel("Retorno Normalizado")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.gcf().autofmt_xdate()
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        logger.info(f"Gráfico guardado en: {save_path}")
    else:
        plt.show()


def backtest(
    save_path: str | None = None,
    coin_id: str = "bitcoin",
    leverage: float = 5.0,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    funding_rate: float = 0.01,
) -> None:
    """Ejecuta el backtest y muestra los resultados con comparación vs holdear."""
    print("\n" + "=" * 60)
    print(f"INICIANDO BACKTEST - Estrategia EMA+RSI Trend ({leverage}x)".center(60))
    print("=" * 60)
    print(f"Moneda: {coin_id.upper()}")
    print(f"Stop Loss: {stop_loss*100}% | Take Profit: {take_profit*100}%")
    print(
        f"Apalancamiento: {leverage}x | "
        f"Tasa de financiamiento anual: {funding_rate*100}%"
    )
    print(f"Fecha actual: {pd.Timestamp.now()}")
    print("-" * 60 + "\n")

    # Ejecutar backtest
    results = run_backtest(
        coin_id=coin_id,
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
    hold_cagr = ((1 + hold_return / 100) ** (365 / len(results["dates"])) - 1) * 100

    # Mostrar resultados
    print("\n" + "=" * 60)
    print("RESULTADOS DEL BACKTEST".center(60))
    print("=" * 60)
    print(f"Período: {results['dates'][0]} a {results['dates'][-1]}")
    print(f"Días de trading: {len(results['dates'])}")
    print(f"\n{'MÉTRICA':<25} {'ESTRATEGIA':<15} {'HOLDEAR':<15}")
    print("-" * 60)
    print(f"{'Capital Inicial:':<25} ${results['initial_capital']:,.2f}")
    hold_final = initial_price + (initial_price * hold_return / 100)
    print(
        f"{'Capital Final:':<25} ${results['final_capital']:,.2f} {hold_final:>15,.2f}"
    )
    total_pct = results["total_return_pct"]
    print(f"{'Retorno Total (%):':<25} {total_pct:>5.2f}% {hold_return:>14.2f}%")
    print(f"{'CAGR (%):':<25} {results['cagr_pct']:>5.2f}% {hold_cagr:>14.2f}%")
    print(f"{'Máximo Drawdown (%):':<25} {results['max_drawdown_pct']:>5.2f}%")
    print(f"{'Operaciones:':<25} {results['total_trades']:>5}")
    print(f"{'Tasa de aciertos (%):':<25} {results['win_rate_pct']:>5.2f}%")
    print(f"{'Profit Factor:':<25} {results['profit_factor']:>5.2f}")
    print(f"{'Ratio de Sharpe:':<25} {results['sharpe_ratio']:>5.2f}")

    # Mostrar comparación de rendimiento
    print("\n" + "-" * 60)
    print("COMPARACIÓN DE RENDIMIENTO".center(60))
    print("-" * 60)
    strat_return = (results["final_capital"] / results["initial_capital"] - 1) * 100
    hold_return = hold_return
    diff = strat_return - hold_return

    if diff > 0:
        print(f"La estrategia superó a holdear por {abs(diff):.2f}%")
    else:
        print(f"La estrategia quedó por debajo de holdear en {abs(diff):.2f}%")

    print("=" * 60 + "\n")

    # Guardar o mostrar gráfico
    if save_path:
        plot_results(results, save_path)
    else:
        plot_results(results)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Backtest de estrategia de trading con margen"
    )
    parser.add_argument(
        "--save", type=str, help="Ruta para guardar el gráfico de resultados"
    )
    parser.add_argument(
        "--coin",
        type=str,
        default="bitcoin",
        help="ID de la criptomoneda (default: bitcoin)",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=5.0,
        help="Nivel de apalancamiento (default: 5.0)",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=0.05,
        help="Stop loss como fracción (default: 0.05)",
    )
    parser.add_argument(
        "--take-profit",
        type=float,
        default=0.10,
        help="Take profit como fracción (default: 0.10)",
    )
    parser.add_argument(
        "--funding-rate",
        type=float,
        default=0.01,
        help="Tasa de financiamiento anual (default: 0.01)",
    )

    args = parser.parse_args()

    backtest(
        save_path=args.save,
        coin_id=args.coin,
        leverage=args.leverage,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
        funding_rate=args.funding_rate,
    )
