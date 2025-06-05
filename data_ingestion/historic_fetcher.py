import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import requests
from datetime import datetime, timezone

from storage.repository import inicializar_bd, guardar_registro, EXCEL_FILE
from analytics.s2f import obtener_valor_s2f, calcular_desviacion


def fetch_historical_prices():
    """Obtiene precios historicos diarios de los ultimos 90 dias."""
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "90", "interval": "daily"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("prices", [])
    except Exception as e:
        print(f"[ADVERTENCIA] Error al obtener datos historicos: {e}")
        return []


def main():
    # Reiniciar el archivo para esta descarga
    if EXCEL_FILE.exists():
        EXCEL_FILE.unlink()
    inicializar_bd()

    registros = fetch_historical_prices()
    for ts, precio in registros:
        fecha = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        s2f = obtener_valor_s2f(fecha)
        desviacion = calcular_desviacion(precio, s2f) if s2f is not None else 0.0
        guardar_registro(fecha, precio, desviacion)

    print(f"Datos historicos guardados en {EXCEL_FILE}")


if __name__ == "__main__":
    main()
