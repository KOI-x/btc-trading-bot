import pandas as pd
import numpy as np
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Añadir el directorio raíz al path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("btc_accumulation_backtest.log"),
    ],
)
logger = logging.getLogger(__name__)


class BTCAccumulationBacktest:
    def __init__(self, initial_usd: float = 10000.0, commission: float = 0.001):
        """
        Inicializa el backtest para estrategia de acumulación de BTC.

        Args:
            initial_usd: Capital inicial en USD
            commission: Comisión por operación (ej: 0.001 = 0.1%)
        """
        self.initial_usd = initial_usd
        self.commission = commission
        self.reset()

    def reset(self):
        """Reinicia el estado del backtest."""
        self.usd_balance = self.initial_usd
        self.btc_balance = 0.0
        self.total_invested = 0.0
        self.btc_accumulated = 0.0
        self.trades = []
        self.equity_curve = []
        self.current_price = 0.0
        self.position_size = 0.0
        self.entry_price = 0.0
        self.in_position = False

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula los indicadores técnicos mejorados."""
        # Medias móviles para tendencia
        df["SMA_50"] = df["Precio USD"].rolling(window=50).mean()
        df["SMA_200"] = df["Precio USD"].rolling(window=200).mean()

        # RSI mejorado con suavizado
        delta = df["Precio USD"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # Bandas de Bollinger mejoradas
        window = 20
        df["SMA_20"] = df["Precio USD"].rolling(window=window).mean()
        df["STD_20"] = df["Precio USD"].rolling(window=window).std()
        df["Upper_Band"] = df["SMA_20"] + (df["STD_20"] * 2)
        df["Lower_Band"] = df["SMA_20"] - (df["STD_20"] * 2)

        # ATR para volatilidad
        high_low = df["Precio Max"] - df["Precio Min"]
        high_close = (df["Precio Max"] - df["Precio USD"].shift()).abs()
        low_close = (df["Precio Min"] - df["Precio USD"].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df["ATR"] = true_range.rolling(window=14).mean()

        # Indicador de tendencia
        df["Tendencia_Alcista"] = df["SMA_50"] > df["SMA_200"]

        # Niveles de soporte y resistencia dinámicos
        df["Soporte_Dinamico"] = df["Precio USD"].rolling(window=50).min()
        df["Resistencia_Dinamica"] = df["Precio USD"].rolling(window=50).max()

        # Distancia a soporte/resistencia
        df["Dist_Soporte"] = (df["Precio USD"] - df["Soporte_Dinamico"]) / df[
            "Soporte_Dinamico"
        ]
        df["Dist_Resistencia"] = (df["Resistencia_Dinamica"] - df["Precio USD"]) / df[
            "Precio USD"
        ]

        return df

    def calculate_position_size(
        self, current_price: float, atr: float, rsi: float, dist_soporte: float
    ) -> float:
        """
        Calcula el tamaño de la posición basado en múltiples factores:
        - Volatilidad (ATR)
        - Nivel de sobreventa (RSI)
        - Distancia al soporte
        """
        # Riesgo base por operación (1% del capital)
        base_risk = self.usd_balance * 0.01

        # Ajustar riesgo según condiciones del mercado
        rsi_factor = max(0, (30 - rsi) / 30)  # 0 a 1, más alto cuando RSI más bajo
        soporte_factor = min(
            1.0, dist_soporte * 10
        )  # Más cerca del soporte = mayor posición

        # Calcular tamaño de posición
        risk_amount = base_risk * (1 + rsi_factor + soporte_factor) / 3

        # Usar ATR para stop loss dinámico (2.5x ATR)
        stop_loss = 2.5 * atr / current_price  # Stop como porcentaje

        # Calcular posición en USD
        position_size = risk_amount / stop_loss

        # Limitar al 10% del saldo disponible
        return min(position_size, self.usd_balance * 0.10)

    def get_buy_conditions(
        self, row: pd.Series, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Evalúa las condiciones de compra y devuelve una tupla con:
        - Si se debe comprar (bool)
        - El motivo de la compra (str)
        """
        # Condición 1: Tendencia alcista
        cond_tendencia = row["Tendencia_Alcista"]

        # Condición 2: RSI en sobreventa
        cond_rsi = row["RSI"] < params.get("rsi_oversold", 30)

        # Condición 3: Precio cerca de la banda inferior de Bollinger
        bollinger_oversold = params.get("bollinger_oversold", 0.05)
        cond_bollinger = row["Precio USD"] < row["Lower_Band"] * (
            1 + bollinger_oversold
        )

        # Condición 4: Precio cerca de soporte dinámico
        cond_soporte = row["Dist_Soporte"] < 0.02  # A menos del 2% del soporte

        # Estrategia principal: Tendencia + RSI + Bollinger
        if cond_tendencia and cond_rsi and cond_bollinger:
            return True, "Tendencia + RSI + Bollinger"

        # Estrategia secundaria: Soporte fuerte + RSI extremo
        if cond_soporte and row["RSI"] < 25:
            return True, "Soporte Fuerte + RSI Extremo"

        return False, ""

    def execute_buy(self, date: datetime, price: float, atr: float):
        """Ejecuta una orden de compra."""
        if self.usd_balance <= 0:
            return False

        # Calcular tamaño de posición
        position_size = self.calculate_position_size(price, atr, 0, 0)
        if position_size <= 0:
            return False

        # Calcular comisión
        commission = position_size * self.commission
        cost = position_size + commission

        # Actualizar saldos
        btc_bought = position_size / price
        self.usd_balance -= cost
        self.btc_balance += btc_bought
        self.total_invested += cost
        self.btc_accumulated += btc_bought

        # Registrar operación
        trade = {
            "date": date,
            "type": "BUY",
            "price": price,
            "btc_amount": btc_bought,
            "usd_amount": position_size,
            "commission": commission,
            "btc_balance": self.btc_balance,
            "usd_balance": self.usd_balance,
        }
        self.trades.append(trade)
        logger.info(
            f"{date} - COMPRA: {btc_bought:.8f} BTC a ${price:,.2f} (${position_size:,.2f} + ${commission:.2f} comisión)"
        )

        return True

    def run(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ejecuta el backtest con la estrategia mejorada."""
        self.reset()

        # Calcular indicadores
        df = self.calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)

        for i, row in df.iterrows():
            if i < 200:  # Esperar a tener suficientes datos
                continue

            self.current_price = row["Precio USD"]

            # Evaluar condiciones de compra
            should_buy, reason = self.get_buy_conditions(row, params or {})

            # Ejecutar compra si se cumplen las condiciones
            if should_buy and self.usd_balance > 10:  # Saldo mínimo para operar
                position_size = self.calculate_position_size(
                    row["Precio USD"], row["ATR"], row["RSI"], row["Dist_Soporte"]
                )

                if position_size > 0:
                    self.execute_buy(row["Fecha"], row["Precio USD"], row["ATR"])

            # Registrar equity diario
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

        # Calcular métricas finales
        final_price = df.iloc[-1]["Precio USD"]
        total_equity = self.usd_balance + (self.btc_balance * final_price)
        btc_value = self.btc_balance * final_price

        # Retorno en USD y BTC
        usd_return = ((total_equity / self.initial_usd) - 1) * 100
        btc_return = (
            (self.btc_balance / (self.initial_usd / df.iloc[0]["Precio USD"])) - 1
        ) * 100

        # Calcular drawdown
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


def load_historical_data(
    file_path: str = "fixtures/price_history/BTC_USD.csv",
) -> pd.DataFrame:
    """Carga y formatea los datos históricos de BTC."""
    try:
        df = pd.read_csv(file_path)

        # Renombrar columnas
        df = df.rename(columns={"date": "Fecha", "price": "Precio USD"})

        # Crear columnas adicionales necesarias
        df["Precio Max"] = df["Precio USD"]
        df["Precio Min"] = df["Precio USD"]
        df["Cierre"] = df["Precio USD"]
        df["Volumen"] = 0

        # Convertir fechas
        df["Fecha"] = pd.to_datetime(df["Fecha"])

        # Ordenar por fecha
        df = df.sort_values("Fecha").reset_index(drop=True)

        logger.info(f"Datos cargados: {df['Fecha'].min()} a {df['Fecha'].max()}")
        return df

    except Exception as e:
        logger.error(f"Error al cargar datos: {str(e)}")
        raise


def optimize_parameters(
    df: pd.DataFrame, initial_usd: float, commission: float
) -> Dict[str, Any]:
    """
    Optimiza los parámetros de la estrategia usando búsqueda en cuadrícula.

    Args:
        df: DataFrame con los datos históricos
        initial_usd: Capital inicial en USD
        commission: Comisión por operación

    Returns:
        Diccionario con los mejores parámetros encontrados
    """
    logger.info("\n" + "=" * 60)
    logger.info("INICIANDO OPTIMIZACIÓN DE PARÁMETROS")
    logger.info("=" * 60)

    # Rangos de parámetros a probar
    param_grid = {
        "rsi_oversold": [25, 30, 35],
        "bollinger_oversold": [0.02, 0.05, 0.08],
        "atr_multiplier": [2.0, 2.5, 3.0],
        "risk_per_trade": [0.005, 0.01, 0.02],
        "min_rsi": [20, 25, 30],
        "trend_filter": [True, False],
    }

    # Generar todas las combinaciones
    from itertools import product

    keys = param_grid.keys()
    values = param_grid.values()
    combinations = list(product(*values))

    best_params = {}
    best_btc = 0
    best_sharpe = -999
    results = []

    total_combinations = len(combinations)
    logger.info(f"Probando {total_combinations} combinaciones de parámetros...")

    for i, combo in enumerate(combinations, 1):
        params = dict(zip(keys, combo))

        # Ejecutar backtest con parámetros actuales
        backtest = BTCAccumulationBacktest(
            initial_usd=initial_usd, commission=commission
        )

        try:
            results_dict = backtest.run(df, params)

            # Calcular ratio de Sharpe (simplificado)
            equity_curve = pd.DataFrame(backtest.equity_curve)
            returns = equity_curve["total_equity"].pct_change().dropna()
            sharpe_ratio = (returns.mean() / returns.std()) * (252**0.5)

            # Guardar resultados
            result = {
                "params": params,
                "btc_accumulated": results_dict["btc_accumulated"],
                "final_usd": results_dict["final_usd"],
                "max_drawdown": results_dict["max_drawdown"],
                "total_trades": len(backtest.trades),
                "sharpe_ratio": sharpe_ratio if not pd.isna(sharpe_ratio) else -999,
            }
            results.append(result)

            # Actualizar mejores parámetros
            if result["btc_accumulated"] > best_btc:
                best_btc = result["btc_accumulated"]
                best_params = params.copy()
                best_sharpe = result["sharpe_ratio"]

            if i % 10 == 0 or i == total_combinations:
                logger.info(
                    f"Progreso: {i}/{total_combinations} | Mejor BTC: {best_btc:.4f} | Sharpe: {best_sharpe:.2f}"
                )

        except Exception as e:
            logger.warning(f"Error con parámetros {params}: {str(e)}")
            continue

    # Mostrar los 5 mejores conjuntos de parámetros
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("btc_accumulated", ascending=False).head()

    logger.info("\n" + "=" * 60)
    logger.info("MEJORES PARÁMETROS ENCONTRADOS")
    logger.info("=" * 60)
    for i, row in results_df.iterrows():
        logger.info(f"\nRanking #{i+1}:")
        logger.info(f"BTC Acumulados: {row['btc_accumulated']:.4f}")
        logger.info(f"Valor Final (USD): ${row['final_usd']:,.2f}")
        logger.info(f"Máximo Drawdown: {row['max_drawdown']:.1f}%")
        logger.info(f"Ratio de Sharpe: {row['sharpe_ratio']:.2f}")
        logger.info("Parámetros:")
        for k, v in row["params"].items():
            logger.info(f"  {k}: {v}")

    return best_params, results_df


def plot_results(results: Dict[str, Any]):
    """Genera gráficos de resultados."""
    try:
        equity = pd.DataFrame(results["equity_curve"])

        # Gráfico 1: Equity Curve
        plt.figure(figsize=(14, 7))

        # Valor total en USD
        plt.subplot(2, 1, 1)
        plt.plot(
            equity["date"],
            equity["total_equity"],
            label="Valor Total (USD)",
            color="blue",
        )
        plt.title("Evolución del Valor Total (USD)")
        plt.grid(True)
        plt.legend()

        # Cantidad de BTC acumulados
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

        plt.tight_layout()

        # Guardar gráfico
        output_file = "btc_accumulation_results.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Gráfico guardado como: {output_file}")

    except Exception as e:
        logger.error(f"Error al generar gráficos: {str(e)}")


def main():
    # Configurar argumentos
    parser = argparse.ArgumentParser(
        description="Backtest de Estrategia de Acumulación de BTC"
    )
    parser.add_argument(
        "--initial-usd", type=float, default=10000.0, help="Capital inicial en USD"
    )
    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Comisión por operación (0.001 = 0.1%)",
    )
    parser.add_argument(
        "--rsi-oversold",
        type=int,
        default=30,
        help="Nivel de RSI para considerar sobreventa",
    )
    parser.add_argument(
        "--bollinger-oversold",
        type=float,
        default=0.05,
        help="Porcentaje por debajo de la banda inferior de Bollinger (0.05 = 5%)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2020-01-01",
        help="Fecha de inicio en formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Fecha de fin en formato YYYY-MM-DD (por defecto: hoy)",
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Ejecutar optimización de parámetros"
    )

    args = parser.parse_args()

    try:
        logger.info("=" * 60)
        logger.info("INICIANDO BACKTEST DE ESTRATEGIA DE ACUMULACIÓN DE BTC")
        logger.info("-" * 60)
        logger.info(f"Período: {args.start_date} a {args.end_date or 'hoy'}")
        logger.info(f"Capital inicial: ${args.initial_usd:,.2f}")
        logger.info(f"Comisión: {args.commission*100:.2f}%")

        if not args.optimize:
            logger.info(f"RSI Sobreventa: {args.rsi_oversold}")
            logger.info(f"Bollinger Sobreventa: {args.bollinger_oversold*100:.1f}%")
        logger.info("=" * 60)

        # Cargar datos
        logger.info("Cargando datos históricos...")
        df = load_historical_data()

        # Filtrar por fechas
        start_date = pd.to_datetime(args.start_date)
        end_date = (
            pd.to_datetime(args.end_date) if args.end_date else pd.to_datetime("today")
        )
        df = df[(df["Fecha"] >= start_date) & (df["Fecha"] <= end_date)]

        if df.empty:
            raise ValueError(
                "No hay datos disponibles para el rango de fechas especificado"
            )

        logger.info(
            f"Datos cargados: {df['Fecha'].min()} a {df['Fecha'].max()} ({len(df)} días)"
        )

        if args.optimize:
            # Ejecutar optimización
            best_params, results_df = optimize_parameters(
                df, args.initial_usd, args.commission
            )

            # Preguntar al usuario si desea ejecutar el backtest con los mejores parámetros
            if (
                input(
                    "\n¿Desea ejecutar el backtest con los mejores parámetros? (s/n): "
                ).lower()
                == "s"
            ):
                args.rsi_oversold = best_params.get("rsi_oversold", 30)
                args.bollinger_oversold = best_params.get("bollinger_oversold", 0.05)
                # Continuar con el backtest normal
            else:
                return

        # Ejecutar backtest con los parámetros especificados
        backtest = BTCAccumulationBacktest(
            initial_usd=args.initial_usd, commission=args.commission
        )

        params = {
            "rsi_oversold": args.rsi_oversold,
            "bollinger_oversold": args.bollinger_oversold,
            "atr_multiplier": 2.5,  # Valor por defecto
            "risk_per_trade": 0.01,  # 1% de riesgo por operación
            "min_rsi": 25,  # RSI mínimo para considerar compra
            "trend_filter": True,  # Filtro de tendencia habilitado
        }

        logger.info("Ejecutando backtest...")
        results = backtest.run(df, params)

        # Mostrar resultados
        btc_price = results["final_price"]
        btc_initial = args.initial_usd / df.iloc[0]["Precio USD"]
        hold_value = btc_initial * btc_price
        strategy_value = results["btc_accumulated"] * btc_price

        print("\n" + "=" * 60)
        print("RESULTADOS DEL BACKTEST".center(60))
        print("=" * 60)
        print(
            f"Período: {df['Fecha'].iloc[0].strftime('%Y-%m-%d')} a {df['Fecha'].iloc[-1].strftime('%Y-%m-%d')}"
        )
        print(f"Días de trading: {len(df)}")
        print("\n" + "-" * 60)
        print(f"{'Capital Inicial (USD):':<30} ${args.initial_usd:,.2f}")
        print(f"{'Valor Final (USD):':<30} ${results['final_usd']:,.2f}")
        print(f"{'Valor HOLD (USD):':<30} ${hold_value:,.2f}")
        print("\n" + "-" * 60)
        print(f"{'BTC Acumulados:':<30} {results['btc_accumulated']:.8f}")
        print(f"{'BTC Inicial (HOLD):':<30} {btc_initial:.8f}")
        print(f"{'Valor en BTC:':<30} ${strategy_value:,.2f}")
        print("\n" + "-" * 60)
        print(f"{'Retorno Total (USD):':<30} {results['usd_return']:,.1f}%")
        print(
            f"{'Retorno HOLD (USD):':<30} {(hold_value/args.initial_usd-1)*100:,.1f}%"
        )
        print(f"{'Retorno Total (BTC):':<30} {results['btc_return']:,.1f}%")
        print(f"{'Máximo Drawdown:':<30} {results['max_drawdown']:,.1f}%")
        print("\n" + "-" * 60)
        print(f"{'Precio Inicial BTC:':<30} ${df.iloc[0]['Precio USD']:,.2f}")
        print(f"{'Precio Final BTC:':<30} ${btc_price:,.2f}")
        print(
            f"{'Variación Precio:':<30} {(btc_price/df.iloc[0]['Precio USD']-1)*100:,.1f}%"
        )
        print("=" * 60 + "\n")

        # Mostrar resumen de operaciones
        if results["trades"]:
            trades = pd.DataFrame(results["trades"])
            print("\n" + "RESUMEN DE OPERACIONES".center(60))
            print("-" * 60)
            print(f"Total operaciones: {len(trades)}")
            print(f"Promedio por operación: ${trades['usd_amount'].mean():,.2f}")
            print(f"Comisión total: ${trades['commission'].sum():,.2f}")

            # Agrupar por año
            trades["year"] = pd.to_datetime(trades["date"]).dt.year
            yearly = (
                trades.groupby("year")
                .agg(
                    {
                        "btc_amount": "sum",
                        "usd_amount": "sum",
                        "commission": "sum",
                        "date": "count",
                    }
                )
                .rename(columns={"date": "trades"})
            )

            print("\n" + "OPERACIONES POR AÑO".center(60))
            print("-" * 60)
            print(
                f"{'Año':<6} {'Operaciones':>12} {'BTC Acum.':>12} {'Invertido (USD)':>15} {'Comisión (USD)':>15}"
            )
            print("-" * 60)
            for year, data in yearly.iterrows():
                print(
                    f"{year:<6} {data['trades']:>12} {data['btc_amount']:>12.8f} {data['usd_amount']:>15,.2f} {data['commission']:>15,.2f}"
                )

        # Generar gráficos
        plot_results(results)

        logger.info("Backtest completado exitosamente")

    except Exception as e:
        logger.error(f"Error durante el backtest: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
