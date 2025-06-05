import pandas as pd


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

    ema10 = df["Precio USD"].ewm(span=10, adjust=False).mean()
    ema50 = df["Precio USD"].ewm(span=50, adjust=False).mean()

    if len(ema10) < 2 or len(ema50) < 2:
        return "HOLD"

    prev_ema10, last_ema10 = ema10.iloc[-2], ema10.iloc[-1]
    prev_ema50, last_ema50 = ema50.iloc[-2], ema50.iloc[-1]

    cross_up = prev_ema10 <= prev_ema50 and last_ema10 > last_ema50
    cross_down = prev_ema10 >= prev_ema50 and last_ema10 < last_ema50

    desviacion = df["Desviación S2F %"].iloc[-1]

    if cross_up and desviacion < 0:
        return "BUY"
    if cross_down and desviacion > 0:
        return "SELL"
    return "HOLD"
