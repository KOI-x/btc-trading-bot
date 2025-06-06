# btc-trading-bot

Sistema modular en Python para trading automático de Bitcoin. Ingesta de datos, análisis de estrategia y ejecución automatizada.

## Descripción del proyecto

Este bot descarga precios históricos de Bitcoin, calcula variaciones y aplica estrategias de trading configurables. Incluye la estrategia combinada de medias móviles exponenciales (EMA) con el modelo Stock-to-Flow (S2F) y otras variantes como mean-reversion con RSI o breakout con ATR.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
```

## Ejecución rápida

```bash
python setup_and_run.py
```

## API REST

Este repositorio incluye un backend en FastAPI listo para servir precios
almacenados en una base de datos SQLite. Para lanzarlo ejecuta:

```bash
uvicorn api.main:app --reload
```

Luego visita `http://localhost:8000/api/prices/{coin_id}` para obtener el
historial diario en formato JSON.

## Dependencias

Las dependencias necesarias se detallan en [requirements.txt](requirements.txt):

- requests
- pandas
- matplotlib
- openpyxl
- schedule

## Contribuir

1. Instala las dependencias de desarrollo:

```bash
pip install -r requirements.txt
```

Formatea tu código con Black e isort:

```bash
black .
isort .
```

Ejecuta Flake8 para asegurar que no haya errores de estilo:

```bash
flake8 --max-line-length=88 --extend-ignore=E203,W503
```

Corre las pruebas y el backtest antes de abrir un pull-request:

```bash
python backtests/ema_s2f_backtest.py
```
Para experimentar con distintas estrategias y parámetros puedes ejecutar el grid search:

```bash
python backtests/run_grid.py
```

## Ejemplo de backtest con verificación de datos

```bash
python tools/ensure_data_and_run.py backtests.ema_s2f_backtest --save equity.png
```
