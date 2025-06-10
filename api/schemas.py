from datetime import date

from pydantic import BaseModel, validator

ALLOWED_COINS = {"bitcoin", "ethereum", "solana"}


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


class PortfolioItem(BaseModel):
    coin_id: str
    amount: float
    buy_date: date

    @validator("coin_id")
    def validate_coin_id(cls, v: str) -> str:
        if v not in ALLOWED_COINS:
            allowed = ", ".join(sorted(ALLOWED_COINS))
            raise ValueError(f"coin_id must be one of: {allowed}")
        return v

    @validator("buy_date")
    def validate_buy_date(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("buy_date must be in the past")
        return v

    @validator("amount")
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class PortfolioEvalRequest(BaseModel):
    portfolio: list[PortfolioItem]
    strategy: str


class PortfolioEvalResponse(BaseModel):
    total_value_now: float
    estrategia_vs_hold: str
    comentario: str
