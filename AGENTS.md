# AGENTS.md

## Arquitectura funcional del bot `btc-trading-bot`

Este sistema automatizado se compone de los siguientes módulos:

### 1. Ingesta de Datos
- `data_ingestion/fetcher.py`: Obtiene el precio actual de Bitcoin desde la API de CoinGecko y lo almacena en Excel.
- `data_ingestion/historic_fetcher.py`: Descarga 90 días de precios históricos desde CoinGecko para backtesting.

### 2. Ejecución Programada
- `data_ingestion/scheduler.py`: Llama al fetcher periódicamente cada 10 minutos usando la librería `schedule`.

### 3. Evaluación de Estrategias
- `strategies/ema_s2f.py`: Implementa una estrategia basada en cruce de medias móviles exponenciales (EMA) y la desviación del modelo Stock-to-Flow (S2F).

### 4. Backtesting
- `backtests/ema_s2f_backtest.py`: Simula la estrategia sobre los datos históricos para evaluar su rentabilidad.

### 5. Visualización
- `analytics/plotter.py`: Genera una imagen con la evolución del capital (equity curve) usando Matplotlib.

### 6. Automatización de Setup
- `setup_and_run.py`: Crea un entorno virtual, instala dependencias, descarga datos históricos y ejecuta el backtest automáticamente.

---

Este archivo resume la función de cada componente y cómo se relacionan dentro del sistema modular.
