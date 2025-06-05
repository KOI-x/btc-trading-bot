import argparse
import subprocess
import sys
from pathlib import Path

EXCEL_FILE = Path("bitcoin_prices.xlsx")


def ensure_data() -> None:
    """Descarga datos historicos si el archivo no existe."""
    if not EXCEL_FILE.exists():
        subprocess.run(
            [sys.executable, "-m", "data_ingestion.historic_fetcher"],
            check=True,
        )


def main() -> None:
    # fmt: off
    parser = argparse.ArgumentParser(
        description="Verifica datos y ejecuta un modulo"
    )
    # fmt: on
    parser.add_argument(
        "module",
        help="Modulo Python a ejecutar (formato paquete.modulo)",
    )
    parser.add_argument(
        "module_args",
        nargs=argparse.REMAINDER,
        help="Argumentos para el modulo",
    )
    args = parser.parse_args()

    ensure_data()

    cmd = [sys.executable, "-m", args.module] + args.module_args
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
