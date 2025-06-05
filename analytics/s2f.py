from pathlib import Path

import pandas as pd

DATA_FILE = Path("data/s2f_model.csv")


def obtener_valor_s2f(fecha: str) -> float | None:
    """Devuelve el valor S2F estimado para la fecha dada.

    Si la fecha no se encuentra en el CSV o hay errores al leerlo,
    se retorna ``None``.
    """
    if not DATA_FILE.exists():
        print("[ADVERTENCIA] No se encontró el archivo s2f_model.csv")
        return None
    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        print(f"[ADVERTENCIA] Error al leer s2f_model.csv: {e}")
        return None

    if "Fecha" not in df.columns or "S2F_Price" not in df.columns:
        print("[ADVERTENCIA] El archivo s2f_model.csv tiene formato incorrecto")
        return None
    try:
        row = df.loc[df["Fecha"] == fecha]
        if not row.empty:
            return float(row.iloc[0]["S2F_Price"])
    except Exception as e:
        print(f"[ADVERTENCIA] Error al obtener valor S2F: {e}")
    return None


def calcular_desviacion(precio_real: float, s2f: float) -> float:
    """Calcula el porcentaje de desviación entre precio real y S2F."""
    if s2f == 0:
        return 0.0
    return ((precio_real - s2f) / s2f) * 100
