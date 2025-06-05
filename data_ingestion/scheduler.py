import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import schedule
import time
from datetime import datetime

import pandas as pd

from data_ingestion.fetcher import obtener_precio_bitcoin
from storage.repository import inicializar_bd, guardar_registro, EXCEL_FILE
from analytics.s2f import obtener_valor_s2f, calcular_desviacion
from strategies.ema_s2f import evaluar_estrategia


def job():
    """Tarea programada para obtener y guardar el precio."""

    try:
        precio = obtener_precio_bitcoin()
        if precio is None:
            return

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fecha_modelo = datetime.now().strftime("%Y-%m-%d")
        s2f_val = obtener_valor_s2f(fecha_modelo)
        desviacion = 0.0
        if s2f_val is not None:
            desviacion = calcular_desviacion(precio, s2f_val)
        variacion = guardar_registro(ahora, precio, desviacion)

        # Cargar el histórico para evaluar la estrategia
        try:
            df = pd.read_excel(EXCEL_FILE)
            senal = evaluar_estrategia(df)
        except Exception as e:
            print(f"[ADVERTENCIA] Error al evaluar estrategia: {e}")
            senal = "HOLD"

        print(
            f"[{ahora}] BTC: ${precio} ({variacion:+.2f}%, S2F {desviacion:+.2f}%) -> {senal}"
        )
    except Exception as e:
        print(f"[ADVERTENCIA] Error en la tarea programada: {e}")


if __name__ == "__main__":
    inicializar_bd()
    schedule.every(10).minutes.do(job)
    job()
    while True:
        schedule.run_pending()
        time.sleep(1)
