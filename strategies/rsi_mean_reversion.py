import pandas as pd


def evaluar_estrategia(
    df: pd.DataFrame, rsi_period: int = 14, overbought: int = 70, oversold: int = 30
) -> str:
    """Estrategia simple de mean-reversion basada en RSI.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame con columnas "Fecha" y "Precio USD".
    rsi_period : int
        Periodo para el cálculo del RSI.
    overbought : int
        Nivel de sobrecompra para generar señal de venta.
    oversold : int
        Nivel de sobreventa para generar señal de compra.

    Returns
    -------
    str
        "BUY", "SELL" o "HOLD".
    """
    if df is None or df.empty or "Precio USD" not in df.columns:
        return "HOLD"

    delta = df["Precio USD"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    roll_up = gain.rolling(rsi_period).mean()
    roll_down = loss.rolling(rsi_period).mean()

    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))

    last_rsi = rsi.iloc[-1]
    if last_rsi < oversold:
        return "BUY"
    if last_rsi > overbought:
        return "SELL"
    return "HOLD"
