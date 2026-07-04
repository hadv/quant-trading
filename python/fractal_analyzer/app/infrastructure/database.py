import asyncpg
from app.core.config import settings
from app.models.domain import DailyCandle
import logging

logger = logging.getLogger(__name__)

class DatabaseRepository:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(settings.DATABASE_URL)
        logger.info("Database connected")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def save_candle(self, candle: DailyCandle):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO local_daily_candles (ticker, trade_date, open_price, high_price, low_price, close_price, volume)
                VALUES ($1, $2::date, $3, $4, $5, $6, $7)
                ON CONFLICT (ticker, trade_date) DO NOTHING
            """, candle.ticker, candle.trade_date, candle.open_price, candle.high_price, candle.low_price, candle.close_price, candle.volume)

    async def save_assessment(self, risk):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO fractal_risk_assessments (ticker, hurst_exponent, fractal_dimension, risk_level, regime, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, risk.ticker, risk.hurst_exponent, risk.fractal_dimension, risk.risk_level, risk.regime, risk.timestamp)

    async def get_historical_prices(self, ticker: str, limit: int = 252) -> list[float]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT close_price FROM local_daily_candles
                WHERE ticker = $1
                ORDER BY trade_date DESC
                LIMIT $2
            """, ticker, limit)
            return [float(r["close_price"]) for r in reversed(rows)]

db_repo = DatabaseRepository()
