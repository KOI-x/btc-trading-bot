import requests
import openpyxl
from datetime import datetime
from pathlib import Path

EXCEL_FILE = Path("bitcoin_prices.xlsx")

def obtener_precio_bitcoin():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    return requests.get(url, timeout=10).json()["bitcoin"]["usd"]

def guardar_precio():
    precio = obtener_precio_bitcoin()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not EXCEL_FILE.exists():
        wb = openpyxl.Workbook()
        wb.active.append(["Fecha", "Precio USD"])
        wb.save(EXCEL_FILE)

    wb = openpyxl.load_workbook(EXCEL_FILE)
    sheet = wb.active
    sheet.append([ahora, precio])
    wb.save(EXCEL_FILE)
    print(f"[{ahora}] BTC: ${precio}")

if __name__ == "__main__":
    guardar_precio()
