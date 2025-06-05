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
