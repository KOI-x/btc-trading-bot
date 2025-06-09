import pandas as pd
import numpy as np
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import matplotlib.pyplot as plt

# Hacer seaborn opcional
try:
    import seaborn as sns

    sns.set()
except ImportError:
    sns = None
    logger = logging.getLogger(__name__)
    logger.warning("Seaborn no está instalado. Los gráficos tendrán un estilo básico.")

from pathlib import Path
import sys

# Añadir el directorio raíz al path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

# Importar la estrategia
from strategies.ema_rsi_trend import evaluar_estrategia

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backtest_ema_rsi_trend.log"),
    ],
)
logger = logging.getLogger(__name__)


class EMARSITrendBacktest:
    def __init__(
        self,
        initial_capital: float = 10000.0,
        leverage: float = 1.0,
        stop_loss: float = 0.10,
        take_profit: float = 0.20,
        commission: float = 0.001,
    ):
        """
        Inicializa el backtest para la estrategia EMA+RSI+Trend.

        Args:
            initial_capital: Capital inicial en USD
            leverage: Apalancamiento a utilizar (1.0 = sin apalancamiento)
            stop_loss: Porcentaje de stop loss (ej: 0.10 = 10%)
            take_profit: Porcentaje de take profit (ej: 0.20 = 20%)
            commission: Comisión por operación (ej: 0.001 = 0.1%)
        """
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.commission = commission

        # Estado del backtest
        self.capital = initial_capital
        self.position = 0.0  # Posición actual en BTC
        self.entry_price = 0.0  # Precio de entrada de la posición actual
        self.trades = []  # Lista para registrar operaciones
        self.equity_curve = []  # Para seguir la curva de capital

    def run(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ejecuta el backtest sobre los datos proporcionados.

        Args:
            df: DataFrame con columnas ['Fecha', 'Precio USD', 'Volumen']
            params: Parámetros personalizados para la estrategia

        Returns:
            Dict con métricas de rendimiento
        """
        logger.info("Iniciando backtest EMA+RSI+Trend...")

        # Inicializar variables
        self.capital = self.initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.equity_curve = []

        # Ordenar por fecha por si acaso
        df = df.sort_values("Fecha").reset_index(drop=True)

        # Asegurarse de que hay suficientes datos
        if len(df) < 100:  # Necesitamos suficientes datos para los indicadores
            raise ValueError("No hay suficientes datos para el backtest")

        # Bucle principal del backtest
        for i in range(
            50, len(df)
        ):  # Empezamos después de tener suficientes datos para los indicadores
            current_row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            current_date = current_row["Fecha"]
            current_price = current_row["Precio USD"]

            # Obtener datos históricos hasta el momento actual
            historical_data = df.iloc[: i + 1].copy()

            # Evaluar la estrategia
            signal = evaluar_estrategia(historical_data, params)

            # Manejar la posición actual
            if self.position > 0:  # Tenemos una posición larga
                # Verificar stop loss y take profit
                pl_pct = (current_price - self.entry_price) / self.entry_price

                if pl_pct <= -self.stop_loss or pl_pct >= self.take_profit:
                    # Cerrar posición por stop loss o take profit
                    close_reason = "TP" if pl_pct > 0 else "SL"
                    self._close_position(current_date, current_price, close_reason)

            # Procesar señales
            if signal == "BUY" and self.position <= 0:
                if self.position < 0:
                    # Cerrar corta si existe
                    self._close_position(current_date, current_price, "SELL signal")
                # Abrir larga
                self._open_position(current_date, current_price, "BUY")

            elif signal == "SELL" and self.position >= 0:
                if self.position > 0:
                    # Cerrar larga si existe
                    self._close_position(current_date, current_price, "SELL signal")
                # Abrir corta (si el apalancamiento lo permite)
                if self.leverage > 1.0:
                    self._open_position(current_date, current_price, "SELL")

            # Registrar el valor del portafolio
            self._update_equity(current_date, current_price)

        # Cerrar cualquier posición abierta al final
        if self.position != 0:
            last_price = df.iloc[-1]["Precio USD"]
            self._close_position(df.iloc[-1]["Fecha"], last_price, "End of backtest")

        # Calcular métricas
        metrics = self._calculate_metrics(df)

        return metrics

    def _open_position(self, date: pd.Timestamp, price: float, signal: str):
        """Abre una nueva posición."""
        position_size = (self.capital * self.leverage) / price

        if signal == "BUY":
            self.position = position_size
        else:  # SELL (corta)
            self.position = -position_size

        self.entry_price = price

        # Registrar la operación
        trade = {
            "date": date,
            "type": "LONG" if signal == "BUY" else "SHORT",
            "price": price,
            "size": position_size,
            "value": position_size * price,
            "commission": position_size * price * self.commission,
        }
        self.trades.append(trade)

        # Aplicar comisión
        self.capital -= trade["commission"]

        logger.info(
            f"{date.date()} - {'Compra' if signal == 'BUY' else 'Venta'} de {position_size:.6f} BTC a ${price:.2f}"
        )

    def _close_position(self, date: pd.Timestamp, price: float, reason: str):
        """Cierra la posición actual."""
        if self.position == 0:
            return

        # Calcular P&L
        pl_pct = (
            (price - self.entry_price)
            / self.entry_price
            * (1 if self.position > 0 else -1)
        )
        pl_usd = abs(self.position) * self.entry_price * pl_pct

        # Registrar cierre de operación
        trade = {
            "date": date,
            "type": "CLOSE",
            "price": price,
            "size": abs(self.position),
            "value": abs(self.position) * price,
            "pl_pct": pl_pct,
            "pl_usd": pl_usd,
            "commission": abs(self.position) * price * self.commission,
            "reason": reason,
        }

        # Actualizar capital
        self.capital += pl_usd
        self.capital -= trade["commission"]

        # Registrar operación
        self.trades.append(trade)

        # Resetear posición
        self.position = 0.0
        self.entry_price = 0.0

        logger.info(f"{date.date()} - Cierre de posición: {reason}")
        logger.info(f"   Precio: ${price:.2f}, P&L: {pl_pct*100:.2f}% (${pl_usd:.2f})")

    def _update_equity(self, date: pd.Timestamp, price: float):
        """Actualiza la curva de capital."""
        position_value = self.position * price
        equity = self.capital + position_value
        self.equity_curve.append(
            {"date": date, "equity": equity, "price": price, "position": self.position}
        )

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula las métricas de rendimiento."""
        if not self.trades:
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
            }

        # Convertir a DataFrame
        trades_df = pd.DataFrame([t for t in self.trades if "pl_pct" in t])

        if trades_df.empty:
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
            }

        # Calcular métricas básicas
        total_return = (self.capital / self.initial_capital - 1) * 100

        # Calcular CAGR
        days = (df["Fecha"].iloc[-1] - df["Fecha"].iloc[0]).days
        years = max(days / 365.25, 0.1)  # Mínimo 0.1 años para evitar división por cero
        cagr = (self.capital / self.initial_capital) ** (1 / years) - 1
        cagr_pct = cagr * 100

        # Calcular métricas de operaciones
        winning_trades = trades_df[trades_df["pl_pct"] > 0]
        losing_trades = trades_df[trades_df["pl_pct"] <= 0]

        total_trades = len(trades_df)
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        avg_win = (
            winning_trades["pl_pct"].mean() * 100 if not winning_trades.empty else 0
        )
        avg_loss = (
            losing_trades["pl_pct"].mean() * 100 if not losing_trades.empty else 0
        )

        profit_factor = (
            abs(winning_trades["pl_usd"].sum() / losing_trades["pl_usd"].sum())
            if not losing_trades.empty and losing_trades["pl_usd"].sum() != 0
            else float("inf")
        )

        # Calcular drawdown
        equity_curve = pd.DataFrame(self.equity_curve)
        equity_curve["peak"] = equity_curve["equity"].cummax()
        equity_curve["drawdown"] = (
            equity_curve["equity"] - equity_curve["peak"]
        ) / equity_curve["peak"]
        max_drawdown = equity_curve["drawdown"].min() * 100

        # Calcular ratio de Sharpe (simplificado)
        daily_returns = equity_curve["equity"].pct_change().dropna()
        sharpe_ratio = (
            np.sqrt(365) * daily_returns.mean() / daily_returns.std()
            if not daily_returns.empty
            else 0
        )

        return {
            "total_return": total_return,
            "cagr": cagr_pct,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_win": (
                winning_trades["pl_pct"].max() * 100 if not winning_trades.empty else 0
            ),
            "max_loss": (
                losing_trades["pl_pct"].min() * 100 if not losing_trades.empty else 0
            ),
            "final_capital": self.capital,
            "equity_curve": equity_curve,
        }


def load_historical_data(
    coin: str = "bitcoin", start_date: str = "2010-01-01"
) -> pd.DataFrame:
    """Carga datos históricos desde el archivo CSV."""
    try:
        # Ruta al archivo de datos históricos
        file_path = Path("fixtures/price_history/BTC_USD.csv")
        if not file_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de datos: {file_path}")

        logger.info(f"Leyendo datos desde: {file_path}")

        # Leer y formatear los datos
        df = pd.read_csv(file_path)

        # Renombrar columnas para mantener consistencia con el formato esperado
        df = df.rename(columns={"date": "Fecha", "price": "Precio USD"})

        # Crear columnas adicionales necesarias para la estrategia
        df["Precio Max"] = df["Precio USD"]
        df["Precio Min"] = df["Precio USD"]
        df["Cierre"] = df["Precio USD"]
        df["Volumen"] = 0  # No hay datos de volumen en el archivo

        # Convertir fechas
        df["Fecha"] = pd.to_datetime(df["Fecha"])

        # Filtrar por fecha de inicio
        start_date = pd.to_datetime(start_date)
        df = df[df["Fecha"] >= start_date].sort_values("Fecha").reset_index(drop=True)

        if df.empty:
            raise ValueError(
                f"No hay datos disponibles después de la fecha de inicio: {start_date}"
            )

        logger.info(
            f"Datos cargados correctamente. Rango de fechas: {df['Fecha'].min()} a {df['Fecha'].max()}"
        )

        return df

    except Exception as e:
        logger.error(f"Error al cargar datos históricos: {str(e)}")
        raise


def plot_results(metrics: Dict[str, Any], df: pd.DataFrame, params: Dict[str, Any]):
    """Genera gráficos de resultados."""
    try:
        if sns is not None:
            sns.set_style("whitegrid")
        else:
            plt.style.use("default")

        initial_capital = metrics.get("initial_capital", 10000.0)

        # Gráfico 1: Equity Curve
        plt.figure(figsize=(14, 7))

        # Normalizar los precios para que comiencen en el capital inicial
        price_norm = df["Precio USD"] / df["Precio USD"].iloc[0] * initial_capital

        # Graficar equity curve y precio
        equity_curve = metrics["equity_curve"]
        plt.plot(
            equity_curve["date"],
            equity_curve["equity"],
            label="Estrategia",
            linewidth=2,
            color="blue",
        )
        plt.plot(
            df["Fecha"],
            price_norm,
            label="HOLD",
            linewidth=1.5,
            linestyle="--",
            color="gray",
        )

        # Marcar entradas y salidas si están disponibles
        if "trades" in metrics and metrics["trades"]:
            trades = pd.DataFrame(metrics["trades"])
            if not trades.empty:
                buys = trades[trades["type"] == "LONG"]
                sells = trades[trades["type"] == "CLOSE"]

                if not buys.empty:
                    plt.scatter(
                        buys["date"],
                        [
                            equity_curve["equity"][i]
                            for i in buys.index
                            if i < len(equity_curve)
                        ],
                        marker="^",
                        color="green",
                        s=100,
                        label="Compra",
                    )
                if not sells.empty:
                    plt.scatter(
                        sells["date"],
                        [
                            equity_curve["equity"][i]
                            for i in sells.index
                            if i < len(equity_curve)
                        ],
                        marker="v",
                        color="red",
                        s=100,
                        label="Venta",
                    )

        plt.title("Rendimiento de la Estrategia vs HOLD", fontsize=16)
        plt.xlabel("Fecha", fontsize=12)
        plt.ylabel("Valor de la Cartera (USD)", fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Ajustar formato de fechas
        plt.gcf().autofmt_xdate()

        # Guardar la figura
        output_file = "ema_rsi_trend_backtest.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Gráfico guardado como: {output_file}")

    except Exception as e:
        logger.error(f"Error al generar gráfico: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


def format_currency(value: float) -> str:
    """Formatea un valor numérico como moneda."""
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:,.1f}M"
    elif abs(value) >= 1_000:
        return f"${value/1_000:,.1f}K"
    return f"${value:,.2f}"


def print_results(metrics: Dict[str, Any], df: pd.DataFrame, params: Dict[str, Any]):
    """Muestra los resultados del backtest en consola."""
    try:
        # Calcular métricas de holdear
        initial_price = df["Precio USD"].iloc[0]
        final_price = df["Precio USD"].iloc[-1]
        hold_return = (final_price - initial_price) / initial_price * 100
        days = (df["Fecha"].iloc[-1] - df["Fecha"].iloc[0]).days
        hold_cagr = (
            ((1 + hold_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0
        )

        # Imprimir encabezado
        print("\n" + "=" * 60)
        print(f"RESULTADOS DEL BACKTEST".center(60))
        print("=" * 60)
        print(
            f"Período: {df['Fecha'].iloc[0].strftime('%Y-%m-%d')} a {df['Fecha'].iloc[-1].strftime('%Y-%m-%d')}"
        )
        print(f"Días de trading: {days}")

        # Imprimir métricas
        print(f"\n{'MÉTRICA':<25} {'ESTRATEGIA':<15} {'HOLDEAR':<15}")
        print("-" * 60)
        print(f"{'Capital Inicial:':<25} {format_currency(metrics['initial_capital'])}")
        print(
            f"{'Capital Final:':<25} {format_currency(metrics['final_capital'])} {format_currency(initial_price * (1 + hold_return/100))}"
        )
        print(
            f"{'Retorno Total (%):':<25} {metrics['total_return']:>5.1f}% {hold_return:>14.1f}%"
        )
        print(f"{'CAGR (%):':<25} {metrics['cagr']:>5.1f}% {hold_cagr:>14.1f}%")
        print(f"{'Máximo Drawdown (%):':<25} {metrics['max_drawdown']:>5.1f}%")
        print(f"{'Operaciones:':<25} {metrics['total_trades']:>5}")
        print(f"{'Tasa de aciertos (%):':<25} {metrics['win_rate']:>5.1f}%")
        print(f"{'Profit Factor:':<25} {metrics['profit_factor']:>5.2f}")
        print(f"{'Ratio de Sharpe:':<25} {metrics['sharpe_ratio']:>5.2f}")

        # Comparación de rendimiento
        print("\n" + "-" * 60)
        print("COMPARACIÓN DE RENDIMIENTO".center(60))
        print("-" * 60)
        strat_return = metrics["total_return"]
        diff = strat_return - hold_return

        if diff > 0:
            print(f"La estrategia superó a holdear por {abs(diff):.1f}%")
        else:
            print(f"La estrategia quedó por debajo de holdear en {abs(diff):.1f}%")

        # Mostrar últimas operaciones si existen
        if "trades" in metrics and metrics["trades"]:
            trades = metrics["trades"]
            print("\n" + "ÚLTIMAS 5 OPERACIONES:".center(60))
            print("-" * 60)
            print(f"{'Fecha':<12} {'Tipo':<6} {'Precio':<12} {'PnL %':<8} {'Capital'}")
            print("-" * 60)
            for trade in trades[-5:]:
                if trade["type"] == "CLOSE":
                    print(
                        f"{trade['date'].strftime('%Y-%m-%d')} {trade['position_type']:<6} "
                        f"${trade['price']:,.2f} {trade.get('pnl_pct', 0):>6.1f}%  "
                        f"${trade.get('capital', 0):,.2f}"
                    )

        print("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Error al mostrar resultados: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Backtest de Estrategia EMA+RSI+Trend")

    # Parámetros de la estrategia
    parser.add_argument(
        "--start-date",
        type=str,
        default="2015-01-01",
        help="Fecha de inicio del backtest (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Fecha de fin del backtest (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--initial-capital", type=float, default=10000.0, help="Capital inicial en USD"
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=1.0,
        help="Apalancamiento a utilizar (1.0 = sin apalancamiento)",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=0.08,
        help="Stop loss como fracción (ej: 0.08 = 8%)",
    )
    parser.add_argument(
        "--take-profit",
        type=float,
        default=0.25,
        help="Take profit como fracción (ej: 0.25 = 25%)",
    )
    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Comisión por operación (ej: 0.001 = 0.1%)",
    )

    # Parámetros de la estrategia
    parser.add_argument(
        "--ema-fast", type=int, default=9, help="Período de la EMA rápida"
    )
    parser.add_argument(
        "--ema-medium", type=int, default=21, help="Período de la EMA media"
    )
    parser.add_argument(
        "--ema-slow", type=int, default=50, help="Período de la EMA lenta"
    )
    parser.add_argument("--rsi-period", type=int, default=14, help="Período del RSI")
    parser.add_argument(
        "--rsi-overbought", type=int, default=70, help="Nivel de sobrecompra del RSI"
    )
    parser.add_argument(
        "--rsi-oversold", type=int, default=30, help="Nivel de sobreventa del RSI"
    )

    args = parser.parse_args()

    try:
        logger.info("=" * 60)
        logger.info("INICIANDO BACKTEST DE ESTRATEGIA EMA+RSI+TREND")
        logger.info("-" * 60)
        logger.info(f"Período: {args.start_date} a {args.end_date}")
        logger.info(f"Capital inicial: ${args.initial_capital:,.2f}")
        logger.info(f"Apalancamiento: {args.leverage}x")
        logger.info(
            f"Stop Loss: {args.stop_loss*100:.1f}%, Take Profit: {args.take_profit*100:.1f}%"
        )
        logger.info(f"Comisión: {args.commission*100:.2f}%")
        logger.info("-" * 60)
        logger.info(f"Parámetros de la estrategia:")
        logger.info(f"  EMAs: {args.ema_fast}/{args.ema_medium}/{args.ema_slow}")
        logger.info(
            f"  RSI: Período={args.rsi_period}, Niveles={args.rsi_oversold}/{args.rsi_overbought}"
        )
        logger.info("=" * 60)

        # Cargar datos históricos
        logger.info(
            f"Cargando datos históricos para BITCOIN desde {args.start_date}..."
        )
        df = load_historical_data("bitcoin", args.start_date)

        if df.empty:
            logger.error("No se encontraron datos para el período seleccionado")
            return

        # Inicializar backtest
        backtest = EMARSITrendBacktest(
            initial_capital=args.initial_capital,
            leverage=args.leverage,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit,
            commission=args.commission,
        )

        # Parámetros de la estrategia
        strategy_params = {
            "ema_fast": args.ema_fast,
            "ema_medium": args.ema_medium,
            "ema_slow": args.ema_slow,
            "rsi_period": args.rsi_period,
            "rsi_overbought": args.rsi_overbought,
            "rsi_oversold": args.rsi_oversold,
        }

        # Ejecutar backtest
        metrics = backtest.run(df, strategy_params)

        # Asegurarse de incluir el capital inicial en las métricas para el gráfico
        metrics["initial_capital"] = args.initial_capital

        # Mostrar resultados en consola
        print_results(metrics, df, strategy_params)

        # Generar gráfico
        plot_results(metrics, df, strategy_params)

    except Exception as e:
        logger.error(f"Error durante la ejecución del backtest: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
