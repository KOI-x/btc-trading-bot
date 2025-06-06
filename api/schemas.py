from datetime import date

from pydantic import BaseModel


class PriceOut(BaseModel):
    date: date
    price_usd: float

    class Config:
        orm_mode = True


class BacktestRequest(BaseModel):
    """Parameters to launch a backtest."""

    strategy: str
    coin_id: str
    params: dict = {}


class BacktestResult(BaseModel):
    """Key metrics returned by a backtest."""

    total_return: float
    cagr: float
    sharpe: float
    equity_curve: list[float]
