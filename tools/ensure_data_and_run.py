#!/usr/bin/env python
"""Utilidad para asegurar datos y ejecutar un módulo.

Si ``bitcoin_prices.xlsx`` no existe, descarga los datos históricos usando
``python -m data_ingestion.historic_fetcher``. Luego ejecuta el módulo
especificado y le pasa cualquier argumento recibido.

Ejemplo:
```
python tools/ensure_data_and_run.py backtests.ema_s2f_backtest --save test.png
```
"""
from __future__ import annotations

import argparse
import runpy
import subprocess
import sys
from pathlib import Path

EXCEL_FILE = Path("bitcoin_prices.xlsx")


def ensure_data() -> None:
    """Descarga los datos históricos si aún no existen."""
    if not EXCEL_FILE.exists():
        subprocess.run(
            [sys.executable, "-m", "data_ingestion.historic_fetcher"], check=True
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure data and run module")
    parser.add_argument(
        "module", help="Módulo a ejecutar, por ejemplo backtests.ema_s2f_backtest"
    )
    args, remainder = parser.parse_known_args()

    ensure_data()

    sys.argv = [args.module] + remainder
    runpy.run_module(args.module, run_name="__main__")


if __name__ == "__main__":
    main()
