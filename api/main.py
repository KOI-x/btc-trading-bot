import asyncio

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from backtests.ema_s2f_backtest import run_backtest

from .database import Base, engine, get_db
from .models import Price
from .schemas import (
    BacktestRequest,
    BacktestResult,
    PortfolioEvalRequest,
    PortfolioEvalResult,
    PriceOut,
)
from analytics import evaluar_vs_hold

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


@app.post("/api/portfolio/eval", response_model=PortfolioEvalResult)
async def portfolio_eval(
    request: PortfolioEvalRequest, db: Session = Depends(get_db)
) -> PortfolioEvalResult:
    """Evaluate a portfolio against holding."""

    if request.strategy != "ema_s2f":
        raise HTTPException(status_code=400, detail="Unsupported strategy")

    loop = asyncio.get_running_loop()
    total_now = 0.0
    total_strategy = 0.0

    for item in request.portfolio:
        latest = (
            db.query(Price)
            .filter(Price.coin_id == item.coin_id)
            .order_by(Price.date.desc())
            .first()
        )
        if latest is None:
            raise HTTPException(status_code=404, detail=f"no prices for {item.coin_id}")
        total_now += latest.price_usd * item.amount

        buy_price = (
            db.query(Price)
            .filter(Price.coin_id == item.coin_id, Price.date == item.buy_date)
            .first()
        )
        if buy_price is None:
            raise HTTPException(
                status_code=404,
                detail=f"no price for {item.coin_id} on {item.buy_date}",
            )
        initial_capital = buy_price.price_usd * item.amount
        result = await loop.run_in_executor(
            None, run_backtest, item.coin_id, initial_capital
        )
        total_strategy += result["equity_curve"][-1]

    status, comentario = evaluar_vs_hold(total_strategy, total_now)
    return PortfolioEvalResult(
        total_value_now=total_now,
        estrategia_vs_hold=status,
        comentario=comentario,
    )
