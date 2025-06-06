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

## Frontend de simulación

Se incluye un componente React llamado `StrategySimulator` (ver
`frontend/StrategySimulator.jsx`) que permite evaluar de forma interactiva
distintas estrategias sobre un monto inicial. El formulario envía los datos al
endpoint `/api/portfolio/eval` y muestra el retorno de la estrategia comparado
con mantener la posición (hold).

El endpoint acepta peticiones `POST` con el siguiente cuerpo JSON:

```json
{
  "portfolio": [
    {"coin_id": "bitcoin", "amount": 0.05, "buy_date": "2023-10-01"}
  ],
  "strategy": "ema_s2f"
}
```

La respuesta indica el valor actual del portafolio y si la estrategia supera al
`buy & hold`:

```json
{
  "total_value_now": 1234.5,
  "estrategia_vs_hold": "mejor",
  "comentario": "Tu estrategia supera al hold en un 12%"
}
```

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

## Soporte Multi-Fiat

La ingesta de precios ahora almacena valores no solo en USD sino también en CLP y EUR.
Se consulta `exchangerate.host` para obtener los tipos de cambio históricos, con
`CoinGecko` como respaldo en caso de error. Las tasas se mantienen en memoria para
evitar llamadas repetidas cuando se procesan varias monedas para la misma fecha.
