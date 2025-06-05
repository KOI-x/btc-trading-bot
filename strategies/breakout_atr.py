import pandas as pd


def evaluar_estrategia(
    df: pd.DataFrame,
    window: int = 20,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
) -> str:
    """Estrategia de breakout con stops basados en ATR.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame con columna "Precio USD".
    window : int
        Ventana para calcular los máximos/mínimos recientes.
    atr_period : int
        Periodo para el cálculo del ATR.
    atr_multiplier : float
        Multiplicador del ATR usado como distancia de stop.

    Returns
    -------
    str
        "BUY", "SELL" o "HOLD".
    """
    if df is None or df.empty or "Precio USD" not in df.columns:
        return "HOLD"

    price = df["Precio USD"]

    # True Range y ATR
    high = price.rolling(2).max()
    low = price.rolling(2).min()
    prev_close = price.shift(1)
    tr = (high - low).combine((price - prev_close).abs(), max)
    tr.rolling(atr_period).mean()

    breakout_up = price.iloc[-1] > price.rolling(window).max().iloc[-2]
    breakout_down = price.iloc[-1] < price.rolling(window).min().iloc[-2]

    if breakout_up:
        return "BUY"
    if breakout_down:
        return "SELL"
    return "HOLD"
