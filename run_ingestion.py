#!/usr/bin/env python
"""Run a sample ingestion for Bitcoin."""
from data_ingestion.historic_fetcher import ingest_price_history


def main() -> None:
    ingest_price_history("bitcoin")


if __name__ == "__main__":
    main()
