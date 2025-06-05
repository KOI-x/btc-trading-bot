# btc-trading-bot

Sistema modular en Python para trading automático de Bitcoin. Ingesta de datos, análisis de estrategia y ejecución automatizada.

## Descripción del proyecto

Este bot descarga precios históricos de Bitcoin, calcula variaciones y aplica una estrategia combinada de medias móviles exponenciales (EMA) con el modelo Stock-to-Flow (S2F) para mostrar resultados de backtesting.

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
