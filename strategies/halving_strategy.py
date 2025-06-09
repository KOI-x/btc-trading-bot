import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_halving_phase(current_date: datetime) -> Tuple[str, float]:
    """
    Determina la fase actual del ciclo de halving y el multiplicador de riesgo.
    """
    halving_dates = [
        datetime(2012, 11, 28),
        datetime(2016, 7, 9),
        datetime(2020, 5, 11),
        datetime(2024, 4, 19),  # Último halving
        datetime(2028, 1, 1),  # Próximo halving estimado
    ]

    last_halving = max([d for d in halving_dates if d <= current_date])
    next_halving = min(
        [d for d in halving_dates if d > current_date],
        default=last_halving + timedelta(days=1460),
    )

    days_since_halving = (current_date - last_halving).days
    total_cycle_days = (next_halving - last_halving).days
    cycle_position = days_since_halving / total_cycle_days

    if cycle_position < 0.25:
        return "acumulacion", 2.0
    elif cycle_position < 0.5:
        return "tendencia_alcista", 1.5
    elif cycle_position < 0.75:
        return "distribucion", 1.0
    else:
        return "pre_halving", 0.5


def calculate_s2f_ratio(block_height: int) -> float:
    """Calcula la relación Stock-to-Flow (S2F)."""
    halving_blocks = 210000
    halving_number = block_height // halving_blocks
    current_supply = 50 * (1 - 0.5**halving_number) * halving_blocks * 2
    blocks_per_year = 6 * 24 * 365
    annual_flow = (6.25 / (2**halving_number)) * blocks_per_year
    return current_supply / annual_flow if annual_flow > 0 else float("inf")


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calcula la Media Móvil Exponencial (EMA)."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calcula el Índice de Fuerza Relativa (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple:
    """Calcula las Bandas de Bollinger."""
    middle_band = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper_band = middle_band + (std * num_std)
    lower_band = middle_band - (std * num_std)
    return upper_band, middle_band, lower_band


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14
) -> pd.Series:
    """Calcula el Índice de Movimiento Direccional Promedio (ADX)."""
    up = high.diff()
    down = low.diff() * -1

    plus_dm = up.where((up > down) & (up > 0), 0)
    minus_dm = down.where((down > up) & (down > 0), 0)

    plus_dm = plus_dm.rolling(window=window).mean()
    minus_dm = minus_dm.rolling(window=window).mean()

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean()

    plus_di = 100 * (plus_dm / atr)
    minus_di = 100 * (minus_dm / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    adx = dx.rolling(window=window).mean()

    return adx


def calculate_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14
) -> pd.Series:
    """Calcula el Rango Verdadero Promedio (ATR)."""
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=window).mean()


def get_technical_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Calcula todos los indicadores técnicos necesarios."""
    df = df.copy()
    close = df["Precio USD"]

    df["EMA_9"] = calculate_ema(close, 9)
    df["EMA_21"] = calculate_ema(close, 21)
    df["EMA_50"] = calculate_ema(close, 50)
    df["EMA_200"] = calculate_ema(close, 200)

    df["RSI"] = calculate_rsi(close, 14)

    df["BB_upper"], df["BB_middle"], df["BB_lower"] = calculate_bollinger_bands(close)

    df["ADX"] = calculate_adx(df["Precio Max"], df["Precio Min"], close)

    df["VOL_MA"] = df["Volumen"].rolling(window=20).mean()

    return df


def evaluar_estrategia_avanzada(
    df: pd.DataFrame, capital: float, params: Dict[str, Any] = None
) -> dict:
    """Estrategia mejorada que combina el ciclo de halving, S2F e indicadores técnicos."""
    default_params = {
        "max_leverage": 3.0,
        "risk_per_trade": 0.02,
        "use_s2f": True,
        "s2f_threshold": 0.3,
        "stop_loss": 0.10,
        "take_profit": 0.30,
    }

    params = {**default_params, **(params or {})}

    try:
        if df is None or df.empty or len(df) < 200:
            return {"signal": "HOLD"}

        df = df.copy()
        current_price = df["Precio USD"].iloc[-1]
        current_date = pd.to_datetime(df["Fecha"].iloc[-1])

        phase, risk_multiplier = get_halving_phase(current_date)

        df = get_technical_indicators(df, params)

        ema_trend = df["EMA_200"].iloc[-1]
        price_above_ema200 = current_price > ema_trend
        ema_cross = df["EMA_9"].iloc[-1] > df["EMA_21"].iloc[-1] > df["EMA_50"].iloc[-1]

        rsi = df["RSI"].iloc[-1]
        rsi_oversold = rsi < 35
        rsi_overbought = rsi > 65

        bb_upper = df["BB_upper"].iloc[-1]
        bb_lower = df["BB_lower"].iloc[-1]
        price_near_bb_lower = current_price < (bb_lower * 1.02)
        price_near_bb_upper = current_price > (bb_upper * 0.98)

        volume_ok = df["Volumen"].iloc[-1] > (df["VOL_MA"].iloc[-1] * 1.5)

        s2f_signal = False
        s2f_ratio = None
        s2f_deviation = 0

        if params["use_s2f"] and "block_height" in params:
            s2f_ratio = calculate_s2f_ratio(params["block_height"])
            price_s2f_model = 0.4 * (s2f_ratio**3)
            s2f_deviation = (current_price - price_s2f_model) / price_s2f_model
            s2f_signal = s2f_deviation < params["s2f_threshold"]

        signal = "HOLD"

        if phase in ["acumulacion", "tendencia_alcista"]:
            if (price_above_ema200 and ema_cross and rsi_oversold) or (
                price_near_bb_lower and volume_ok
            ):
                signal = "BUY"

        elif phase in ["distribucion", "pre_halving"]:
            if rsi_overbought or price_near_bb_upper:
                signal = "SELL"

        if (
            params["use_s2f"]
            and "block_height" in params
            and s2f_ratio is not None
            and s2f_ratio > 50
            and s2f_deviation > 1.0
        ):
            signal = "SELL"

        position_size = capital * params["max_leverage"] * risk_multiplier

        atr = calculate_atr(df["Precio Max"], df["Precio Min"], df["Precio USD"]).iloc[
            -1
        ]
        if atr / current_price > 0.05:
            position_size *= 0.7

        stop_loss_pct = params.get("stop_loss", 0.10)
        take_profit_pct = params.get("take_profit", 0.30)

        if phase == "acumulacion":
            stop_loss_pct *= 1.2
            take_profit_pct *= 1.5
        elif phase == "pre_halving":
            stop_loss_pct *= 0.8
            take_profit_pct *= 0.8

        return {
            "signal": signal,
            "entry_price": current_price,
            "stop_loss": current_price * (1 - stop_loss_pct),
            "take_profit": current_price * (1 + take_profit_pct),
            "position_size": position_size,
            "leverage": min(params["max_leverage"] * risk_multiplier, 5.0),
            "current_stop_loss": stop_loss_pct,
            "current_take_profit": take_profit_pct,
            "phase": phase,
            "rsi": rsi,
        }

    except Exception as e:
        logger.error(f"Error en estrategia avanzada: {str(e)}", exc_info=True)
        return {"signal": "HOLD"}


def evaluar_estrategia(df: pd.DataFrame, params: Dict[str, Any] = None) -> str:
    """Wrapper para compatibilidad con el backtest existente."""
    if df is None or df.empty:
        return "HOLD"

    capital = params.get("capital", 10000.0) if params else 10000.0
    result = evaluar_estrategia_avanzada(df, capital, params)
    return result.get("signal", "HOLD")


def estimate_block_height(date: datetime) -> int:
    """Estima la altura del bloque para una fecha dada."""
    genesis_block_date = datetime(2009, 1, 3)
    blocks_per_hour = 6
    hours_since_genesis = (date - genesis_block_date).total_seconds() / 3600
    return int(hours_since_genesis * blocks_per_hour)
