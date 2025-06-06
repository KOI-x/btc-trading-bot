from datetime import date

from pydantic import BaseModel


class PriceOut(BaseModel):
    date: date
    price_usd: float

    class Config:
        orm_mode = True
