import pandas as pd
import logging
import numpy as np
from typing import Tuple, Dict, Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def evaluar_estrategia(df: pd.DataFrame, params: Dict[str, Any] = None) -> str:
    """Estrategia de Trading EMA + RSI + Tendencia

    Estrategia que combina múltiples medias móviles exponenciales (EMA) con RSI
    y análisis de volumen para identificar tendencias y puntos de entrada/salida.

    Parámetros:
        df: DataFrame con columnas ["Fecha", "Precio USD", "Variación %"]
        params: Diccionario con parámetros personalizables de la estrategia

    Retorna:
        str: 'BUY', 'SELL' o 'HOLD' según las condiciones
    """
    # Parámetros por defecto
    default_params = {
        "ema_fast": 10,
        "ema_medium": 21,
        "ema_slow": 50,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "volume_ma": 20,
        "min_volume_multiplier": 1.5,
    }

    # Combinar parámetros por defecto con los proporcionados
    params = {**default_params, **(params or {})}

    # Validar datos de entrada
    if df is None or df.empty or len(df) < params["ema_slow"]:
        logger.warning("Datos insuficientes para el análisis")
        return "HOLD"

    try:
        # Hacer una copia para no modificar el original
        df = df.copy()

        # Calcular EMAs
        df["EMA_FAST"] = (
            df["Precio USD"].ewm(span=params["ema_fast"], adjust=False).mean()
        )
        df["EMA_MED"] = (
            df["Precio USD"].ewm(span=params["ema_medium"], adjust=False).mean()
        )
        df["EMA_SLOW"] = (
            df["Precio USD"].ewm(span=params["ema_slow"], adjust=False).mean()
        )

        # Calcular RSI
        delta = df["Precio USD"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=params["rsi_period"]).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=params["rsi_period"]).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # Calcular volumen promedio si está disponible
        if "Volumen" in df.columns:
            df["VOL_MA"] = df["Volumen"].rolling(window=params["volume_ma"]).mean()
            volume_ok = df["Volumen"].iloc[-1] > (
                df["VOL_MA"].iloc[-1] * params["min_volume_multiplier"]
            )
        else:
            volume_ok = True  # Si no hay datos de volumen, ignorar esta condición

        # Obtener valores actuales
        current = df.iloc[-1]
        prev = df.iloc[-2]

        # Condiciones de compra
        buy_conditions = [
            current["EMA_FAST"] > current["EMA_MED"],  # EMA rápida sobre la media
            current["EMA_MED"] > current["EMA_SLOW"],  # EMA media sobre la lenta
            current["RSI"] < params["rsi_overbought"],  # RSI no sobrecomprado
            volume_ok,  # Volumen por encima del promedio
        ]

        # Condiciones de venta
        sell_conditions = [
            current["EMA_FAST"] < current["EMA_MED"],  # EMA rápida bajo la media
            current["EMA_MED"] < current["EMA_SLOW"],  # EMA media bajo la lenta
            current["RSI"] > params["rsi_oversold"],  # RSI no sobrevendido
            volume_ok,  # Volumen por encima del promedio
        ]

        # Verificar cruces recientes para mayor sensibilidad
        fast_cross_above_med = (prev["EMA_FAST"] <= prev["EMA_MED"]) and (
            current["EMA_FAST"] > current["EMA_MED"]
        )
        fast_cross_below_med = (prev["EMA_FAST"] >= prev["EMA_MED"]) and (
            current["EMA_FAST"] < current["EMA_MED"]
        )

        # Generar señales
        if all(buy_conditions) or (
            fast_cross_above_med and current["EMA_MED"] > current["EMA_SLOW"]
        ):
            logger.info(
                "SEÑAL DE COMPRA - Tendencias alcistas y condiciones favorables"
            )
            return "BUY"

        elif all(sell_conditions) or (
            fast_cross_below_med and current["EMA_MED"] < current["EMA_SLOW"]
        ):
            logger.info("SEÑAL DE VENTA - Tendencias bajistas y condiciones favorables")
            return "SELL"

        # Si no hay señales claras, mantener posición actual
        logger.info("Sin señales de operación claras")
        return "HOLD"

    except Exception as e:
        logger.error(f"Error en la estrategia: {str(e)}", exc_info=True)
        return "HOLD"
