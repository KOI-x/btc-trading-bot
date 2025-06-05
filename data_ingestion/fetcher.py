import requests
from datetime import datetime

from storage.repository import guardar_registro


def obtener_precio_bitcoin() -> float | None:
    """Obtiene el precio de Bitcoin desde CoinGecko.

    Si la solicitud falla o los datos no son válidos, se muestra una advertencia
    y se devuelve ``None`` para que el programa pueda continuar.
    """

    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        precio = data.get("bitcoin", {}).get("usd")
        if precio is None:
            raise ValueError("respuesta sin precio")
        return precio
    except Exception as e:
        print(f"[ADVERTENCIA] Error al obtener el precio desde CoinGecko: {e}")
        return None


def guardar_precio():
    """Obtiene el precio y lo almacena en la base de datos."""

    precio = obtener_precio_bitcoin()
    if precio is None:
        return

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variacion = guardar_registro(ahora, precio)
    print(f"[{ahora}] BTC: ${precio} ({variacion:+.2f}%)")


if __name__ == "__main__":
    guardar_precio()
