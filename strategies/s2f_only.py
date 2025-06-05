import pandas as pd


def evaluar_estrategia(
    df: pd.DataFrame,
    threshold_buy: float = -20.0,
    threshold_sell: float = 20.0,
) -> str:
    """Estrategia basada únicamente en la desviación al modelo S2F.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame con columna "Desviación S2F %".
    threshold_buy : float
        Desviación (en %) por debajo de la cual se genera compra.
    threshold_sell : float
        Desviación (en %) por encima de la cual se genera venta.

    Returns
    -------
    str
        "BUY", "SELL" o "HOLD".
    """
    if df is None or df.empty or "Desviación S2F %" not in df.columns:
        return "HOLD"

    dev = df["Desviación S2F %"].iloc[-1]
    if dev <= threshold_buy:
        return "BUY"
    if dev >= threshold_sell:
        return "SELL"
    return "HOLD"
