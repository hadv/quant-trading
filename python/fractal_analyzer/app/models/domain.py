from datetime import datetime
from pydantic import BaseModel

class FractalRisk(BaseModel):
    ticker: str
    hurst_exponent: float
    fractal_dimension: float
    risk_level: float
    regime: str
    timestamp: datetime

class DailyCandle(BaseModel):
    ticker: str
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
