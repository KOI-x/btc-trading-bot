# Backtest de Aportes Mensuales

Este documento explica cómo probar la estrategia de acumulación de BTC simulando depósitos mensuales de capital. No modifica la lógica de `BTCAccumulationBacktest`, sino que provee un `runner` que inyecta fondos cada mes y luego ejecuta la estrategia.

## Parámetros principales

- **capital_inicial**: monto en USD con el que se comienza la simulación.
- **aportes_mensuales**: lista de valores en USD a depositar cada mes. Pueden variar entre 100 y 300 USD o cualquier valor.
- **fecha_inicio / fecha_fin**: rango de la prueba. Debe existir información histórica de precios para este periodo.
- **señales de compra**: se mantienen las de la estrategia original (RSI ≤ 30 y precio 8 % por debajo de la banda inferior de Bollinger). Si no se cumple la señal en un mes, el efectivo aportado se mantiene sin operar.

## Ejecución

1. Asegúrate de contar con el histórico en `fixtures/price_history/BTC_USD.csv`.
2. Ejecuta desde la raíz del proyecto:
   ```bash
   python -m backtests.monthly_injection_runner \
       --initial-usd 1000 \
       --monthly 200 150 250 300 \
       --start 2021-01-01 \
       --end 2022-12-31
   ```
   El parámetro `--monthly` acepta una secuencia de valores para cada mes.
3. El script mostrará la evolución del saldo en BTC y USD mes a mes y generará un gráfico en `results/`.

## Notas

- Se reutiliza `BTCAccumulationBacktest` para la ejecución diaria; solamente se actualiza el balance de USD al inicio de cada mes.
- Si la lista de aportes es más corta que el número de meses del periodo, los aportes restantes se consideran cero.
- Puedes modificar fácilmente la lista de aportes para probar diferentes escenarios de inversión periódica.

## Comparar distintos puntos de entrada

Con `backtests.monthly_entry_comparison` puedes evaluar la estrategia en varios periodos de inicio y compararla contra un DCA simple.

```bash
python -m backtests.monthly_entry_comparison \
    --start-dates 2020-01-01 2022-01-01 2024-01-01 \
    --months 24 \
    --monthly 150 150 150 150
```

El script imprimirá una tabla con BTC acumulado por la estrategia, BTC acumulado por un HODL con los mismos aportes mensuales, la diferencia porcentual y el valor final en USD.


## Automatizar varios periodos

Para ejecutar la estrategia en una secuencia de periodos y compararla contra un DCA equivalente, utiliza `backtests.multi_period_backtest_runner`.

```bash
python -m backtests.multi_period_backtest_runner \
    --monthly 150 150 150 150 \
    --csv resultados.csv
```

El archivo se guardará automáticamente en la carpeta `results/` como
`results/resultados.csv`.

Si no indicas periodos, se probarán cinco rangos predefinidos que cubren distintos ciclos de mercado. Puedes personalizar los periodos pasando pares de fechas (`inicio fin`) al argumento `--periods`.

Para explorar la sensibilidad de la estrategia también puedes ejecutar con `--sensitivity`, lo que calcula el retorno promedio y la ventaja frente al DCA variando el RSI (25,30,35) y el umbral de Bollinger (0.05,0.08,0.10). Si añades `--plot` se guardará un gráfico comparando cada ciclo.

### Columnas del CSV

Cada periodo genera tres filas: una para la estrategia, otra para el DCA de referencia y una fila de `resumen` que compara ambas. Las columnas son:

- `periodo` y `ciclo`: rango analizado y tipo de mercado.
- `tipo`: `estrategia`, `dca` o `resumen`.
- `usd_invertido`: capital acumulado invertido hasta ese periodo.
- `btc_final` y `usd_final`: saldos obtenidos al final.
- `retorno_btc_pct` y `retorno_usd_pct`: rendimiento porcentual respecto al capital invertido.
- `max_drawdown`: peor caída porcentual del valor total durante el periodo.
- `tiempo_en_perdida_pct`: porcentaje de días en que el valor estuvo por debajo del capital invertido.
- `sharpe_ratio`: relación retorno/volatilidad mensual (aproximada).
- `señales_disparadas`: cantidad de compras ejecutadas por la estrategia.
- `fecha_ultima_compra`: última fecha en que se realizó una operación.
- `ventaja_pct_vs_dca`: diferencia de rendimiento en USD de la estrategia contra el DCA.

Al final del reporte se imprime un **Resumen global** con promedios de retornos, porcentaje de ciclos donde la estrategia supera al DCA y el total de señales disparadas.

## Runner híbrido con detección de entornos

El archivo `backtests/hybrid_trend_backtest_runner.py` permite evaluar compras
mensuales ajustadas al entorno de mercado utilizando la SMA200. Cada mes se
clasifica el mercado como **bull**, **bear** o **neutral** y, si es alcista o
bajista, se calcula un aporte dinámico:

```
aporte = base + (precio_actual / SMA50 - 1) * factor_ajuste
```

La compra adaptativa solo se ejecuta si el RSI de 45 periodos supera el umbral
definido por `--rsi-threshold` (si se indica `0` se desactiva el filtro). En
entorno neutral se aplica el monto indicado en `--fixed`.

### Parámetros adicionales

- `--base`: aporte base común para bull y bear.
- `--factor-bull`: multiplicador aplicado en entornos alcistas.
- `--factor-bear`: multiplicador aplicado en entornos bajistas.
- `--fixed`: monto a invertir en entornos neutrales.
- `--rsi-threshold`: nivel mínimo del RSI(45) para activar la compra adaptativa (0 lo desactiva).
- `--env-threshold`: margen sobre la SMA200 que define bull o bear.
- `--use-onchain`: fusiona las métricas de Glassnode para detectar el entorno.

### Columnas extra del CSV

- `entorno`: estado del mercado al cierre del periodo.
- `tendencia`: cruce final de SMA50 y SMA200.
- `modo_estrategia`: `adaptativa` o `dca`.
- `btc_final`: cantidad de BTC acumulados.
- `ventaja_btc_pct`: diferencia porcentual de BTC frente a un DCA.
- `sopr` y `exchange_net_flow`: métricas on-chain del último día (si se usa la bandera).

### Ejemplo

```bash
python -m backtests.hybrid_trend_backtest_runner \
    --base 100 --factor-bull 200 --factor-bear 150 --fixed 50 \
    --start-date 2018-01-01 --end-date 2021-12-31 \
    --use-onchain
```
Si no se cuenta con la clave de Glassnode, define `EXCHANGE_NET_FLOW_CSV` y
`SOPR_CSV` con las rutas a los CSV descargados manualmente.
