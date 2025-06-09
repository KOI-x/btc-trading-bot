import os
import sys
from pathlib import Path
import logging
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Verificar que todas las dependencias estén instaladas."""
    required = ["pandas", "numpy", "matplotlib", "sqlalchemy", "python-dateutil"]
    missing = []

    for package in required:
        try:
            __import__(package)
            logger.info(f"✓ {package} está instalado")
        except ImportError:
            missing.append(package)

    if missing:
        logger.error(f"Faltan las siguientes dependencias: {', '.join(missing)}")
        logger.info("Puedes instalarlas con: pip install " + " ".join(missing))
        return False
    return True


def setup_directories():
    """Crear directorios necesarios si no existen."""
    data_dir = Path("data")
    logs_dir = Path("logs")

    for directory in [data_dir, logs_dir]:
        directory.mkdir(exist_ok=True)
        logger.info(f"Directorio verificado: {directory}")


def initialize_database():
    """Inicializar la base de datos SQLite."""
    from config import DATABASE_URL
    from storage.database import init_engine, init_db

    try:
        engine = init_engine(DATABASE_URL)
        init_db(engine)
        logger.info("Base de datos inicializada correctamente")
        return True
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("CONFIGURACIÓN DEL SISTEMA DE TRADING".center(60))
    print("=" * 60 + "\n")

    # Verificar dependencias
    print("\n[1/3] Verificando dependencias...")
    if not check_dependencies():
        sys.exit(1)

    # Configurar directorios
    print("\n[2/3] Configurando directorios...")
    setup_directories()

    # Inicializar base de datos
    print("\n[3/3] Inicializando base de datos...")
    if not initialize_database():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("CONFIGURACIÓN COMPLETADA CON ÉXITO".center(60))
    print("=" * 60)
    print("\nAhora puedes ejecutar el backtest con el siguiente comando:")
    print("python backtests/halving_backtest.py --start-date 2016-01-01")


if __name__ == "__main__":
    main()
