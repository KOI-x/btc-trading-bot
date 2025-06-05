import subprocess
import sys
from pathlib import Path

# --------------------------- Utilidades ------------------------------------


def ensure_package(pkg: str) -> None:
    """Importa un paquete o lo instala si falta."""
    try:
        __import__(pkg)
    except ImportError:
        print(f"Instalando paquete requerido: {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])


def verificar_archivo_excel(path: Path) -> "pd.DataFrame | None":
    """Comprueba existencia y columnas del Excel."""
    import pandas as pd  # se asegura mediante ensure_package

    if not path.exists():
        print(f"[ERROR] No se encontró el archivo {path.name}.")
        return None

    try:
        df = pd.read_excel(path)
    except Exception as e:
        print(f"[ERROR] No se pudo leer {path.name}: {e}")
        return None

    columnas = set(df.columns)
    obligatorias = {"Fecha", "Precio USD"}
    if not obligatorias.issubset(columnas):
        faltantes = obligatorias - columnas
        print(
            f"[ERROR] El archivo no contiene las columnas obligatorias: {', '.join(faltantes)}"
        )
        return None

    opcionales = [c for c in ("Variación %", "Desviación S2F %") if c not in columnas]
    if opcionales:
        print(
            "[ADVERTENCIA] El archivo no contiene las columnas opcionales: "
            + ", ".join(opcionales)
        )

    return df


def verificar_carpetas(rutas: list[Path]) -> bool:
    """Comprueba que existan las carpetas necesarias."""
    ok = True
    for ruta in rutas:
        if not ruta.is_dir():
            print(f"[ERROR] No se encontró la carpeta {ruta}/")
            ok = False
    return ok


def agregar_sys_path(root: Path) -> None:
    """Asegura que el proyecto esté en sys.path para importar estrategias."""
    try:
        import strategies  # noqa: F401
    except Exception:
        sys.path.append(str(root))
        try:
            import strategies  # noqa: F401
        except Exception:
            print("[ERROR] No se pudo importar el módulo 'strategies'.")
            sys.exit(1)


# --------------------------- Backtest --------------------------------------


def ejecutar_backtest(df, rsi_period: int, overbought: int, oversold: int) -> None:
    from math import sqrt

    import matplotlib.pyplot as plt
    import pandas as pd

    from strategies.rsi_mean_reversion import evaluar_estrategia

    capital = 10000.0
    position = False
    entry_price = 0.0
    trades = 0
    wins = 0
    equity_curve: list[float] = []

    for i in range(len(df)):
        sub_df = df.iloc[: i + 1]
        signal = evaluar_estrategia(
            sub_df, rsi_period=rsi_period, overbought=overbought, oversold=oversold
        )
        price = df.loc[i, "Precio USD"]

        if signal == "BUY" and not position:
            position = True
            entry_price = price
            trades += 1
        elif signal == "SELL" and position:
            if price > entry_price:
                wins += 1
            capital *= price / entry_price
            position = False

        equity = capital * (price / entry_price) if position else capital
        equity_curve.append(equity)

    if position:
        price = df.iloc[-1]["Precio USD"]
        if price > entry_price:
            wins += 1
        capital *= price / entry_price
        equity_curve[-1] = capital

    win_rate = (wins / trades * 100) if trades else 0.0

    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdowns = (equity_series - running_max) / running_max
    max_drawdown = drawdowns.min() * 100

    days = (
        pd.to_datetime(df["Fecha"].iloc[-1]) - pd.to_datetime(df["Fecha"].iloc[0])
    ).days
    cagr = (capital / 10000.0) ** (365 / days) - 1 if days else 0.0

    returns = equity_series.pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * sqrt(365)) if not returns.empty else 0.0

    print("\n------ Resultados del Backtest ------")
    print(f"Valor final de la cuenta: ${capital:.2f}")
    print(f"Cantidad de operaciones: {trades}")
    print(f"Win-rate: {win_rate:.2f}%")
    print(f"Max drawdown: {max_drawdown:.2f}%")
    print(f"CAGR: {cagr * 100:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")

    plt.figure()
    plt.plot(df["Fecha"], equity_curve, label="Equity Curve")
    plt.xlabel("Fecha")
    plt.ylabel("Capital ($)")
    plt.title("Estrategia RSI Mean Reversion")
    plt.legend()
    plt.tight_layout()
    plt.savefig("equity_curve.png")
    print("Curva de capital guardada en equity_curve.png")


# --------------------------- Punto de entrada ------------------------------


def main() -> None:
    root = Path(__file__).resolve().parent

    # Verificar/instalar paquetes
    for pkg in ["pandas", "matplotlib", "openpyxl"]:
        ensure_package(pkg)

    import pandas as pd  # noqa: E402

    # Verificar archivo Excel
    excel_file = root / "bitcoin_prices.xlsx"
    df = verificar_archivo_excel(excel_file)
    if df is None:
        sys.exit(1)

    # Verificar carpetas requeridas
    if not verificar_carpetas([root / "strategies", root / "backtests"]):
        sys.exit(1)

    # Ajustar sys.path si es necesario
    agregar_sys_path(root)

    # Ejecutar backtest con estrategia predeterminada
    ejecutar_backtest(df, rsi_period=14, overbought=70, oversold=30)


if __name__ == "__main__":
    main()
