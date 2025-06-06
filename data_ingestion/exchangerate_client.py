from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from typing import Dict

import requests

from .errors import IngestionError

_BASE_URL = "https://api.exchangerate.host/"
_rates_cache: Dict[date, Dict[str, Decimal]] = {}


def _fetch_rates(day: date) -> Dict[str, Decimal]:
    url = f"{_BASE_URL}{day.isoformat()}"
    params = {"base": "USD", "symbols": "CLP,EUR"}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    rates = data.get("rates", {})
    return {
        "CLP": Decimal(str(rates.get("CLP"))),
        "EUR": Decimal(str(rates.get("EUR"))),
    }


def _fetch_from_coingecko(day: date) -> Dict[str, Decimal]:
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/history"
    params = {"date": day.strftime("%d-%m-%Y"), "localization": "false"}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    md = data.get("market_data", {}).get("current_price", {})
    usd = Decimal(str(md.get("usd")))
    clp_rate = Decimal(str(md.get("clp"))) / usd
    eur_rate = Decimal(str(md.get("eur"))) / usd
    return {"CLP": clp_rate, "EUR": eur_rate}


def get_rates_for_date(day: date) -> Dict[str, Decimal]:
    if day in _rates_cache:
        return _rates_cache[day]

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            result = _fetch_rates(day)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2**attempt)
    else:
        # Fallback to CoinGecko
        for attempt in range(3):
            try:
                result = _fetch_from_coingecko(day)
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(2**attempt)
        else:
            raise IngestionError(f"failed to fetch rates: {last_exc}")

    _rates_cache[day] = result
    return result
