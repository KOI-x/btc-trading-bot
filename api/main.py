import asyncio
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from analytics.performance import comparar_vs_hold
from analytics.portfolio import analizar_portafolio
from backtests.ema_s2f_backtest import run_backtest
from storage.database import get_price_on, init_db, init_engine

from .database import Base, engine, get_db
from .models import Price
from .schemas import (
    BacktestRequest,
    BacktestResult,
    PortfolioEvalRequest,
    PortfolioEvalResponse,
    PriceOut,
)

app = FastAPI()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)


@app.get("/api/prices/{coin_id}", response_model=list[PriceOut])
def get_prices(coin_id: str, db: Session = Depends(get_db)):
    query = db.query(Price).filter(Price.coin_id == coin_id)
    prices = query.order_by(Price.date).all()
    if not prices:
        raise HTTPException(status_code=404, detail="coin_id not found")
    return prices


@app.post("/api/backtest", response_model=BacktestResult)
async def backtest_endpoint(request: BacktestRequest) -> BacktestResult:
    """Execute a backtest asynchronously and return its metrics."""

    if request.strategy != "ema_s2f":
        raise HTTPException(status_code=400, detail="Unsupported strategy")

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        run_backtest,
        request.coin_id,
        request.params.get("initial_capital", 10000.0),
    )
    return BacktestResult(**result)


@app.post("/api/portfolio/eval", response_model=PortfolioEvalResponse)
async def eval_portfolio(request: PortfolioEvalRequest) -> PortfolioEvalResponse:
    """Evaluate a portfolio against a hold approach."""

    if request.strategy != "ema_s2f":
        raise HTTPException(status_code=400, detail="Unsupported strategy")

    if not request.portfolio:
        raise HTTPException(status_code=400, detail="Portfolio cannot be empty")

    ops = [
        {"coin_id": it.coin_id, "date": it.buy_date, "amount": it.amount}
        for it in request.portfolio
    ]
    df_port = analizar_portafolio(ops)
    if df_port.empty:
        raise HTTPException(status_code=400, detail="No price data for portfolio")

    total_value_now = float(df_port["total_value_usd"].iloc[-1])

    loop = asyncio.get_running_loop()

    engine = init_engine("sqlite:///prices.sqlite")
    init_db(engine)
    Session = sessionmaker(bind=engine)

    initial_total = 0.0
    final_hold_total = 0.0
    final_strategy_total = 0.0

    for it in request.portfolio:
        with Session() as session:
            start_price = get_price_on(session, it.coin_id, it.buy_date)
            end_price = get_price_on(session, it.coin_id, date.today())
        if start_price is None or end_price is None:
            raise HTTPException(status_code=400, detail="Missing price data")

        initial_cap = it.amount * start_price
        initial_total += initial_cap
        final_hold_total += it.amount * end_price
        result = await loop.run_in_executor(
            None,
            run_backtest,
            it.coin_id,
            initial_cap,
            it.buy_date.isoformat(),
        )
        cmp_result = comparar_vs_hold(
            it.coin_id,
            it.buy_date.isoformat(),
            date.today().isoformat(),
            result["equity_curve"],
        )
        final_strategy_total += initial_cap * (1 + cmp_result["retorno_estrategia"])

    retorno_hold = final_hold_total / initial_total - 1
    retorno_estrategia = final_strategy_total / initial_total - 1

    if abs(retorno_estrategia - retorno_hold) < 1e-9:
        comparacion = "igual"
    elif retorno_estrategia > retorno_hold:
        comparacion = "mejor"
    else:
        comparacion = "peor"

    diff_pct = (retorno_estrategia - retorno_hold) * 100
    if diff_pct > 0:
        comentario = f"Tu estrategia supera al hold en un {diff_pct:.0f}%"
    elif diff_pct < 0:
        comentario = f"Hold era mejor por {abs(diff_pct):.0f}%"
    else:
        comentario = "La estrategia obtuvo el mismo retorno que holdear"

    return PortfolioEvalResponse(
        total_value_now=total_value_now,
        estrategia_vs_hold=comparacion,
        comentario=comentario,
    )
