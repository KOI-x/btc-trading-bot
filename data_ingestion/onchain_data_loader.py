from __future__ import annotations

"""Helpers to load on-chain metrics from CSV or Glassnode API."""

from datetime import datetime
import os
from typing import Optional

import pandas as pd
import requests


_DEF_START = "2010-01-01"


def _read_csv(path: str, col_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "t" in df.columns and "v" in df.columns:
        df["date"] = pd.to_datetime(df["t"], unit="s")
        df = df.rename(columns={"v": col_name})
    elif "date" in df.columns and col_name in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    else:
        raise ValueError(f"Formato inesperado en {path}")
    return df[["date", col_name]]


def _fetch_metric(endpoint: str, col_name: str, start: str, end: str) -> pd.DataFrame:
    api_key = os.getenv("GLASSNODE_API_KEY")
    if not api_key:
        raise RuntimeError("GLASSNODE_API_KEY no configurada")
    url = f"https://api.glassnode.com/v1/metrics/{endpoint}"
    params = {
        "a": "BTC",
        "api_key": api_key,
        "i": "24h",
    }
    if start:
        params["s"] = int(pd.Timestamp(start).timestamp())
    if end:
        params["u"] = int(pd.Timestamp(end).timestamp())
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["t"], unit="s")
    df = df.rename(columns={"v": col_name})
    return df[["date", col_name]]


def load_onchain_data(
    exchange_net_flow_csv: Optional[str] = None,
    sopr_csv: Optional[str] = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Return daily exchange net flow and SOPR data."""
    start = start_date or _DEF_START
    end = end_date or datetime.utcnow().strftime("%Y-%m-%d")

    if os.getenv("GLASSNODE_API_KEY") and not (exchange_net_flow_csv and sopr_csv):
        flow = _fetch_metric("transactions/exchange_net_flow", "exchange_net_flow", start, end)
        sopr = _fetch_metric("transactions/sopr", "sopr", start, end)
    else:
        if not exchange_net_flow_csv or not sopr_csv:
            raise ValueError("Se requieren rutas de CSV si no hay API key")
        flow = _read_csv(exchange_net_flow_csv, "exchange_net_flow")
        sopr = _read_csv(sopr_csv, "sopr")

    df = pd.merge(flow, sopr, on="date", how="inner")
    df = df.sort_values("date").reset_index(drop=True)
    return df

