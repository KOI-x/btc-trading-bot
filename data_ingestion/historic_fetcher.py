"""Download historical prices and store them in SQLite."""

from __future__ import annotations

import logging
import random
import time
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Tuple

import requests
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session as DBSession

from config import DATABASE_URL
from storage.database import PriceHistory, init_db, init_engine

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("data_ingestion.log")],
)
logger = logging.getLogger(__name__)

# Configuración de la API
MAX_RETRIES = 3
INITIAL_DELAY = 2  # segundos
MAX_DELAY = 60  # segundos
RATE_LIMIT_DELAY = 65  # segundos (la API tiene un límite de 50-100 llamadas/minuto)
DAYS_PER_REQUEST = 90  # Número máximo de días por solicitud (límite de la API)


def exponential_backoff(retries: int) -> float:
    """Calcula el tiempo de espera exponencial con jitter."""
    if retries == 0:
        return 0
    return min(INITIAL_DELAY * (2 ** (retries - 1)) + random.uniform(0, 1), MAX_DELAY)


def _daterange(start: date_type, end: date_type) -> Iterable[date_type]:
    """Yield dates from start to end (inclusive)."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _fetch_coin_gecko_range(
    coin_id: str, start_date: date_type, end_date: date_type, vs_currency: str = "usd"
) -> Tuple[Dict[date_type, Dict[str, float]], bool]:
    """Fetch price data from CoinGecko API for a date range."""
    start_ts = int(
        datetime.combine(
            start_date, datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
    )
    end_ts = int(
        datetime.combine(
            end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
    )

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {"vs_currency": vs_currency, "from": start_ts, "to": end_ts}

    try:
        logger.info(f"Solicitando datos desde {start_date} hasta {end_date}...")
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 429:  # Rate limit
            logger.warning(
                f"Rate limit alcanzado. Esperando {RATE_LIMIT_DELAY} segundos..."
            )
            time.sleep(RATE_LIMIT_DELAY)
            return {}, True

        response.raise_for_status()
        data = response.json()

        # Procesar los datos en el formato de la API de rango
        result = {}
        if "prices" in data and data["prices"]:
            for ts, price in data["prices"]:
                dt = datetime.fromtimestamp(ts // 1000, tz=timezone.utc).date()
                if dt not in result:
                    result[dt] = {"usd": price}

        return result, False

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error fetching data for range {start_date} to {end_date}: {str(e)}"
        )
        return {}, False


def _get_existing_dates(session: DBSession, coin_id: str) -> set[date_type]:
    """Obtener las fechas que ya están en la base de datos."""
    existing = session.query(PriceHistory.date).filter_by(coin_id=coin_id).all()
    return {r[0] for r in existing}


def _save_price_data(
    session: DBSession, coin_id: str, date: date_type, prices: Dict[str, float]
) -> bool:
    """Guardar los datos de precios en la base de datos."""
    try:
        price_record = (
            session.query(PriceHistory).filter_by(coin_id=coin_id, date=date).first()
        )

        if price_record:
            # Actualizar registro existente
            price_record.price_usd = prices.get("usd")
            price_record.price_eur = prices.get("eur")
            price_record.price_clp = prices.get("clp")
        else:
            # Crear nuevo registro
            price_record = PriceHistory(
                coin_id=coin_id,
                date=date,
                price_usd=prices.get("usd"),
                price_eur=prices.get("eur"),
                price_clp=prices.get("clp"),
            )
            session.add(price_record)

        session.commit()
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Error al guardar datos para {date}: {str(e)}")
        return False


def fetch_historical_data(
    coin_id: str, start_date: date_type, end_date: date_type
) -> Dict[date_type, Dict[str, float]]:
    """Obtener datos históricos para un rango de fechas."""
    all_data = {}
    current_start = start_date

    while current_start <= end_date:
        current_end = min(
            current_start + timedelta(days=DAYS_PER_REQUEST - 1), end_date
        )

        for attempt in range(MAX_RETRIES + 1):
            data, rate_limited = _fetch_coin_gecko_range(
                coin_id, current_start, current_end
            )

            if rate_limited and attempt < MAX_RETRIES:
                delay = exponential_backoff(attempt)
                logger.info(
                    "Reintentando en %.1f segundos... (Intento %s/%s)",
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue

            if data:
                all_data.update(data)
                # Esperar un tiempo aleatorio entre solicitudes
                time.sleep(random.uniform(1.0, 2.0))
                break

            if attempt == MAX_RETRIES:
                logger.warning(
                    "No se pudieron obtener datos para %s - %s después de %s intentos",
                    current_start,
                    current_end,
                    MAX_RETRIES,
                )

        current_start = current_end + timedelta(days=1)

    return all_data


def ingest_price_history(coin_id: str, days: int = 30) -> None:
    """Download price data for ``coin_id`` and store it."""
    engine = init_engine(DATABASE_URL)
    init_db(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    end_date = datetime.now(tz=timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    logger.info(f"Buscando datos desde {start_date} hasta {end_date}")

    try:
        # Obtener fechas existentes
        existing_dates = _get_existing_dates(session, coin_id)
        logger.info(f"{len(existing_dates)} fechas ya existen en la base de datos")

        # Determinar fechas faltantes
        all_dates = set(_daterange(start_date, end_date))
        missing_dates = sorted(all_dates - existing_dates)

        if not missing_dates:
            logger.info("No hay fechas nuevas para descargar")
            return

        logger.info(f"Descargando {len(missing_dates)} fechas faltantes...")

        # Obtener datos faltantes en lotes
        missing_start = min(missing_dates)
        missing_end = max(missing_dates)

        # Obtener datos históricos
        price_data = fetch_historical_data(coin_id, missing_start, missing_end)

        # Guardar los datos
        saved_count = 0
        for date in missing_dates:
            if date in price_data:
                if _save_price_data(session, coin_id, date, price_data[date]):
                    saved_count += 1

        logger.info(f"Proceso completado. Se guardaron {saved_count} nuevos registros.")

    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario")
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
    finally:
        session.close()
        logger.info("Proceso de carga de datos históricos finalizado")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Descargar datos históricos de criptomonedas"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Número de días de datos históricos a descargar (por defecto: 30)",
    )
    parser.add_argument(
        "--coin",
        type=str,
        default="bitcoin",
        help="ID de la criptomoneda (por defecto: bitcoin)",
    )

    args = parser.parse_args()

    logger.info(f"Iniciando descarga de {args.days} días para {args.coin}...")
    ingest_price_history(args.coin, args.days)
