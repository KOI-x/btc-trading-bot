"""
Estrategia de Acumulación de BTC para ejecución en producción.

Esta estrategia implementa el algoritmo de acumulación de BTC probado en backtest,
adaptado para operar en tiempo real con un exchange de criptomonedas.
"""

import argparse
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import ccxt
import pandas as pd
from dotenv import load_dotenv

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/btc_accumulation.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("btc_accumulation")


class BTCAccumulationStrategy:
    def __init__(
        self,
        exchange: str,
        symbol: str,
        initial_usd: float,
        params: Optional[Dict] = None,
    ):
        """
        Inicializa la estrategia de acumulación de BTC.

        Args:
            exchange: Nombre del exchange (ej: 'binance')
            symbol: Par de trading (ej: 'BTC/USDT')
            initial_usd: Capital inicial en USD
            params: Parámetros de la estrategia
        """
        self.symbol = symbol
        self.initial_usd = initial_usd

        # Parámetros por defecto
        self.params = {
            "rsi_oversold": 30,
            "bollinger_oversold": 0.08,
            "atr_multiplier": 3.0,
            "risk_per_trade": 0.005,  # 0.5% de riesgo por operación
            "min_rsi": 30,
            "trend_filter": False,
            "commission": 0.001,  # 0.1% de comisión
        }

        if params:
            self.params.update(params)

        # Inicializar el exchange
        self.exchange = self._init_exchange(exchange)

        # Estado de la estrategia
        self.running = False
        self.last_update = None

        # Inicializar saldo simulado
        self.simulated_balance = {"USDT": float(initial_usd), "BTC": 0.0}

        # Crear directorios necesarios
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    def _init_exchange(self, exchange_name: str) -> ccxt.Exchange:
        """Inicializa la conexión con el exchange."""
        try:
            # Cargar credenciales desde variables de entorno
            load_dotenv()
            api_key = os.getenv(f"{exchange_name.upper()}_API_KEY")
            secret = os.getenv(f"{exchange_name.upper()}_SECRET")

            if not api_key or not secret:
                raise ValueError(f"Faltan credenciales para {exchange_name}")

            # Crear instancia del exchange
            exchange_class = getattr(ccxt, exchange_name.lower())
            exchange = exchange_class(
                {
                    "apiKey": api_key,
                    "secret": secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "spot",
                    },
                }
            )

            # Verificar conexión
            exchange.fetch_balance()
            logger.info(f"Conectado a {exchange_name} exitosamente")
            return exchange

        except Exception as e:
            logger.error(f"Error al conectar con {exchange_name}: {str(e)}")
            raise

    def fetch_historical_data(
        self, timeframe: str = "1d", limit: int = 200
    ) -> pd.DataFrame:
        """Obtiene datos históricos del exchange."""
        try:
            logger.info(
                f"Obteniendo {limit} velas de {self.symbol} en timeframe {timeframe}"
            )
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("date")

            return df

        except Exception as e:
            logger.error(f"Error al obtener datos históricos: {str(e)}")
            raise

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula los indicadores técnicos."""
        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # Bandas de Bollinger
        window = 20
        df["sma_20"] = df["close"].rolling(window=window).mean()
        df["std_20"] = df["close"].rolling(window=window).std()
        df["upper_band"] = df["sma_20"] + (df["std_20"] * 2)
        df["lower_band"] = df["sma_20"] - (df["std_20"] * 2)

        # ATR para volatilidad
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df["atr"] = true_range.rolling(window=14).mean()

        return df

    def should_buy(self, df: pd.DataFrame) -> bool:
        """Determina si se debe ejecutar una orden de compra."""
        last_row = df.iloc[-1]

        # Condiciones de compra
        rsi_condition = last_row["rsi"] < self.params["rsi_oversold"]
        bollinger_condition = last_row["close"] < (
            last_row["lower_band"] * (1 - self.params["bollinger_oversold"])
        )

        return rsi_condition and bollinger_condition

    def calculate_position_size(self, current_price: float, atr: float) -> float:
        """Calcula el tamaño de la posición basado en el riesgo."""
        # Obtener balance actual
        balance = self.get_balance()
        usd_balance = balance.get("free", {}).get("USDT", 0)

        if usd_balance <= 0:
            return 0

        # Calcular tamaño de posición basado en el riesgo
        risk_amount = usd_balance * self.params["risk_per_trade"]
        stop_loss = self.params["atr_multiplier"] * atr / current_price

        if stop_loss <= 0:
            return 0

        position_size = risk_amount / stop_loss

        # Asegurar que no exceda el saldo disponible
        max_position = usd_balance / current_price
        return min(position_size, max_position * 0.99)  # Dejar margen para comisiones

    def get_balance(self) -> Dict[str, Any]:
        """Obtiene el balance de la cuenta."""
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            logger.error(f"Error al obtener balance: {str(e)}")
            return {}

    def place_buy_order(self, amount: float) -> Optional[Dict]:
        """Ejecuta una orden de compra."""
        try:
            symbol = self.symbol
            price = self.exchange.fetch_ticker(symbol)["ask"]

            # Calcular cantidad con precisión correcta
            amount = float(self.exchange.amount_to_precision(symbol, amount))

            if amount <= 0:
                logger.warning("Monto de compra inválido")
                return None

            logger.info(
                f"[SIMULACIÓN] Orden de compra: {amount} {symbol} a ~${price:.2f}"
            )

            # Actualizar saldo simulado
            cost = amount * price
            self.simulated_balance["USDT"] -= cost
            self.simulated_balance["BTC"] += amount
            logger.info(
                "[SIMULACIÓN] Saldo actualizado - USD: $%.2f, BTC: %.8f",
                self.simulated_balance["USDT"],
                self.simulated_balance["BTC"],
            )

            # Simular orden para pruebas
            return {
                "id": "simulated_order",
                "symbol": symbol,
                "side": "buy",
                "type": "market",
                "amount": amount,
                "price": price,
                "cost": cost,
                "status": "closed",
                "timestamp": int(time.time() * 1000),
            }

        except Exception as e:
            logger.error(f"Error al ejecutar orden de compra: {str(e)}")
            return None

    def run(self):
        """Ejecuta la estrategia en bucle."""
        self.running = True
        logger.info("Iniciando estrategia de acumulación de BTC")

        try:
            while self.running:
                try:
                    # Obtener datos históricos
                    df = self.fetch_historical_data()

                    # Calcular indicadores
                    df = self.calculate_indicators(df)

                    # Verificar si es momento de comprar
                    if self.should_buy(df):
                        last_row = df.iloc[-1]
                        position_size = self.calculate_position_size(
                            last_row["close"], last_row["atr"]
                        )

                        if position_size > 0:
                            self.place_buy_order(position_size)

                    # Mostrar estado actual
                    self.print_status(df)

                    # Esperar antes de la siguiente iteración (1 hora)
                    time.sleep(3600)

                except KeyboardInterrupt:
                    logger.info("Deteniendo estrategia...")
                    self.running = False
                    break

                except Exception as e:
                    logger.error(f"Error en el bucle principal: {str(e)}")
                    time.sleep(60)  # Esperar 1 minuto antes de reintentar

        finally:
            self.cleanup()

    def print_status(self, df: pd.DataFrame):
        """Muestra el estado actual de la estrategia."""
        last_row = df.iloc[-1]

        # Obtener saldos reales para referencia
        real_balance = self.get_balance()
        real_usd = real_balance.get("free", {}).get("USDT", 0)
        real_btc = real_balance.get("free", {}).get("BTC", 0)

        # Usar saldos simulados
        usd_balance = self.simulated_balance["USDT"]
        btc_balance = self.simulated_balance["BTC"]
        total_balance = usd_balance + (btc_balance * last_row["close"])

        # Mostrar estado
        print("\n" + "=" * 80)
        print("ESTRATEGIA DE ACUMULACIÓN DE BTC - MODO SIMULACIÓN")
        print("=" * 80)
        print(f"Exchange: {self.exchange.id.upper()}")
        print(f"Par: {self.symbol}")
        print(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)
        print(f"Precio BTC: ${last_row['close']:.2f}")
        print(f"RSI: {last_row['rsi']:.2f}")
        print(f"Banda Inferior: ${last_row['lower_band']:.2f}")
        print(f"Banda Superior: ${last_row['upper_band']:.2f}")
        print("-" * 80)
        print("SALDOS SIMULADOS:")
        print(f"  USD: ${usd_balance:.2f}")
        print(f"  BTC: {btc_balance:.8f} (${btc_balance * last_row['close']:.2f})")
        print(f"  TOTAL: ${total_balance:.2f}")
        print("-" * 80)
        print("SALDOS REALES (solo referencia):")
        print(f"  USD: ${real_usd:.2f}")
        print(f"  BTC: {real_btc:.8f} (${real_btc * last_row['close']:.2f})")
        print("=" * 80 + "\n")

    def cleanup(self):
        """Limpia los recursos antes de cerrar."""
        logger.info("Cerrando conexiones...")
        if hasattr(self, "exchange"):
            try:
                if hasattr(self.exchange, "close"):
                    self.exchange.close()
                elif hasattr(self.exchange, "session") and self.exchange.session:
                    self.exchange.session.close()
            except Exception as e:
                logger.warning(f"Error al cerrar la conexión: {str(e)}")
        logger.info("Estrategia detenida")


def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Estrategia de Acumulación de BTC")
    parser.add_argument(
        "--exchange",
        type=str,
        default="binance",
        help="Exchange a utilizar (ej: binance, kucoin)",
    )
    parser.add_argument(
        "--symbol", type=str, default="BTC/USDT", help="Par de trading (ej: BTC/USDT)"
    )
    parser.add_argument(
        "--initial-usd", type=float, default=1000.0, help="Capital inicial en USD"
    )
    parser.add_argument(
        "--rsi-oversold",
        type=float,
        default=30.0,
        help="Nivel de RSI para considerar sobreventa",
    )
    parser.add_argument(
        "--bollinger-oversold",
        type=float,
        default=0.08,
        help="Porcentaje por debajo de la banda inferior de Bollinger",
    )

    args = parser.parse_args()

    # Crear directorio de logs si no existe
    os.makedirs("logs", exist_ok=True)

    # Configurar parámetros
    params = {
        "rsi_oversold": args.rsi_oversold,
        "bollinger_oversold": args.bollinger_oversold,
    }

    try:
        # Inicializar y ejecutar estrategia
        strategy = BTCAccumulationStrategy(
            exchange=args.exchange,
            symbol=args.symbol,
            initial_usd=args.initial_usd,
            params=params,
        )

        strategy.run()

    except KeyboardInterrupt:
        logger.info("Estrategia detenida por el usuario")
    except Exception as e:
        logger.error(f"Error en la estrategia: {str(e)}", exc_info=True)
    finally:
        if "strategy" in locals():
            strategy.cleanup()


if __name__ == "__main__":
    main()
