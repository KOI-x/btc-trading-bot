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

La ruta de la base de datos puede configurarse con la variable de entorno
`DATABASE_URL` (por defecto `sqlite:///./data/database.db`).
⚙️ Crea un archivo `.env` con dicha variable. Puedes basarte en
`.env.example`.

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

Además existe el componente `EvaluationHistory` (ver
`frontend/EvaluationHistory.jsx`) que consulta el endpoint `/api/evaluations` y
muestra en una tabla el historial de evaluaciones con fecha, moneda,
estrategia y el diferencial de retorno frente a un enfoque de holdear. Las
filas pueden ordenarse por fecha o `coin_id` y al hacer clic se despliegan los
detalles completos de la evaluación.

Para guardar estos resultados se añadió el endpoint `/api/evaluation/export`.
Recibe el mismo JSON que `/api/portfolio/eval` y permite indicar el formato
`format` como `csv` o `pdf`. El archivo descargable incluye coin_id, estrategia,
fecha, retornos, curva de equity y una sugerencia final comparando con holdear.

## Dependencias

Las dependencias necesarias se detallan en [requirements.txt](requirements.txt):

- requests
- pandas
- matplotlib
- openpyxl
- reportlab
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

### Hooks de pre-commit

1. Instala dependencias de desarrollo  
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Activa los hooks

   ```bash
   pre-commit install
   ```

Para formatear todo el proyecto de golpe:

```bash
pre-commit run --all-files
```

También puedes instalarlos con Make:

```make
make hooks
```


## Ejemplo de backtest con verificación de datos

```bash
python tools/ensure_data_and_run.py backtests.ema_s2f_backtest --save equity.png
```

## Guía paso a paso para backtesting

1. Inicializa (o reinicia) la base de datos:

```bash
python -m tools.db init
# o para empezar desde cero
python tools/reset_db.py --force
```

2. Ejecuta el backtest usando `python -m` para que funcione el `PYTHONPATH`:

```bash
python -m tools.ensure_data_and_run backtests.ema_s2f_backtest --save equity.png
```

Si recibes un error `OperationalError` sobre columnas faltantes, elimina el
archivo `data/database.db` y vuelve a ejecutar los comandos anteriores. En caso
de un error 429 por demasiadas peticiones a CoinGecko, espera unos minutos y
vuelve a intentar.

## Soporte Multi-Fiat

La ingesta de precios ahora almacena valores no solo en USD sino también en CLP y EUR.
Se consulta `exchangerate.host` para obtener los tipos de cambio históricos, con
`CoinGecko` como respaldo en caso de error. Las tasas se mantienen en memoria para
evitar llamadas repetidas cuando se procesan varias monedas para la misma fecha.

## Migraciones de base de datos

El proyecto utiliza **Alembic** para versionar el esquema. Los comandos
principales están disponibles en `tools/db.py`:

```bash
python tools/db.py init    # crea el archivo de base de datos y aplica migraciones
python tools/db.py upgrade # aplica los cambios pendientes
```

`init` es seguro de ejecutar varias veces; si la base de datos ya existe,
simplemente se ejecutan las migraciones.

## Cargar fixtures locales

Los archivos CSV con historial desde 2020 se encuentran en
`fixtures/price_history`. Para precargar la base de datos sin conexión ejecuta:

```bash
python -m tools.load_fixtures
```

Luego puedes correr el bot o los backtests incluso sin acceso a internet.

## Ejecutar el frontend React

El directorio [`frontend`](frontend) contiene una aplicación creada con Vite.
Para probar la interfaz web de simulación:

```bash
cd frontend
npm install
npm run dev
```

Esto inicia el servidor en `http://localhost:5173` y permite interactuar con los
endpoints del backend.
