from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

EXCEL_FILE = Path("bitcoin_prices.xlsx")


def plot():
    if not EXCEL_FILE.exists():
        print("No se encontró el archivo de datos.")
        return

    df = pd.read_excel(EXCEL_FILE)
    if not {"Fecha", "Precio USD", "Variación %"}.issubset(df.columns):
        print("El archivo no contiene las columnas necesarias.")
        return

    df["Fecha"] = pd.to_datetime(df["Fecha"])

    fig, ax1 = plt.subplots()
    color1 = "tab:blue"
    ax1.set_xlabel("Fecha")
    ax1.set_ylabel("Precio USD", color=color1)
    ax1.plot(df["Fecha"], df["Precio USD"], color=color1, label="Precio USD")
    ax1.tick_params(axis="y", labelcolor=color1)

    ax2 = ax1.twinx()
    color2 = "tab:red"
    ax2.set_ylabel("Variación %", color=color2)
    ax2.plot(df["Fecha"], df["Variación %"], color=color2, label="Variación %")
    ax2.tick_params(axis="y", labelcolor=color2)

    fig.tight_layout()
    plt.title("Evolución del precio de Bitcoin")
    plt.show()


if __name__ == "__main__":
    plot()
