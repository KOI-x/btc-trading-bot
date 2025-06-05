import pandas as pd

# Parámetros de la estrategia ajustados para obtener
# más operaciones sobre un periodo de 90 días
FAST_EMA = 2
SLOW_EMA = 5
# Umbral de desviación S2F para validar las señales
BUY_THRESHOLD = 5     # señal de compra si desviación < 5%
SELL_THRESHOLD = -5   # señal de venta si desviación > -5%


def evaluar_estrategia(df: pd.DataFrame) -> str:
    """Evalúa una estrategia basada en EMAs y desviación S2F.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame con columnas "Fecha", "Precio USD", "Variación %", "Desviación S2F %".

    Returns
    -------
    str
        'BUY', 'SELL' o 'HOLD' según las condiciones.
    """
    if df is None or df.empty or "Precio USD" not in df.columns:
        return "HOLD"

    ema_fast = df["Precio USD"].ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = df["Precio USD"].ewm(span=SLOW_EMA, adjust=False).mean()

    if len(ema_fast) < 2 or len(ema_slow) < 2:
        return "HOLD"

    prev_ema_fast, last_ema_fast = ema_fast.iloc[-2], ema_fast.iloc[-1]
    prev_ema_slow, last_ema_slow = ema_slow.iloc[-2], ema_slow.iloc[-1]

    cross_up = prev_ema_fast <= prev_ema_slow and last_ema_fast > last_ema_slow
    cross_down = prev_ema_fast >= prev_ema_slow and last_ema_fast < last_ema_slow

    desviacion = df["Desviación S2F %"].iloc[-1]

    if cross_up and desviacion < BUY_THRESHOLD:
        return "BUY"
    if cross_down and desviacion > SELL_THRESHOLD:
        return "SELL"
    return "HOLD"
