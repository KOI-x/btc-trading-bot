import asyncio

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from backtests.ema_s2f_backtest import run_backtest

from .database import Base, engine, get_db
from .models import Price
from .schemas import BacktestRequest, BacktestResult, PriceOut

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
