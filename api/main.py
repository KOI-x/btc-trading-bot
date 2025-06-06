from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Price
from .schemas import PriceOut

app = FastAPI()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)


@app.get("/api/prices/{coin_id}", response_model=list[PriceOut])
def get_prices(coin_id: str, db: Session = Depends(get_db)):
    prices = db.query(Price).filter(Price.coin_id == coin_id).order_by(Price.date).all()
    if not prices:
        raise HTTPException(status_code=404, detail="coin_id not found")
    return prices
