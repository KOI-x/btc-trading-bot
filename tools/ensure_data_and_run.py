#!/usr/bin/env python
"""Utilidad para asegurar datos y ejecutar un módulo.

Si no hay suficientes datos en la base de datos, intenta cargar desde los fixtures.
Si los fixtures no están disponibles, descarga los datos históricos.
"""
from __future__ import annotations

import argparse
import logging
import runpy
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from storage.database import PriceHistory
from storage.database import init_db as db_init_db
from storage.database import init_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def has_sufficient_data(min_days: int = 30) -> bool:
    """Verifica si hay suficientes datos en la base de datos."""
    try:
        engine = init_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Verificar si hay al menos min_days de datos
        count = session.query(PriceHistory).count()
        logger.info(f"Se encontraron {count} registros en la base de datos")
        return count >= min_days
    except Exception as e:
        logger.warning(f"Error al verificar datos en la base de datos: {e}")
        return False


def load_fixtures() -> bool:
    """Intenta cargar datos desde los fixtures."""
    try:
        logger.info("Intentando cargar datos desde fixtures...")
        subprocess.run(
            [sys.executable, "-m", "tools.load_fixtures"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"No se pudieron cargar los fixtures: {e.stderr}")
        return False


def download_historical_data() -> bool:
    """Descarga los datos históricos si es necesario."""
    try:
        logger.info("Descargando datos históricos...")
        subprocess.run(
            [sys.executable, "-m", "data_ingestion.historic_fetcher"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al descargar datos históricos: {e.stderr}")
        return False


def ensure_data() -> None:
    """Asegura que haya datos disponibles para el backtest."""
    if has_sufficient_data():
        logger.info("Suficientes datos encontrados en la base de datos")
        return

    # Intentar cargar desde fixtures primero
    if load_fixtures() and has_sufficient_data():
        return

    # Si no hay suficientes datos en los fixtures, intentar descargar
    if not download_historical_data():
        logger.warning(
            "No se pudieron obtener datos. Continuando con los datos disponibles."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure data and run module")
    parser.add_argument(
        "module", help="Módulo a ejecutar, por ejemplo backtests.ema_s2f_backtest"
    )
    args, remainder = parser.parse_known_args()

    try:
        # Inicializar la base de datos
        engine = init_engine(DATABASE_URL)
        db_init_db(engine)

        # Asegurar que hay datos
        ensure_data()

        # Ejecutar el módulo solicitado
        sys.argv = [args.module] + remainder
        runpy.run_module(args.module, run_name="__main__")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
