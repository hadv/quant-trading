import asyncpg
import os
import logging
from app.models.domain import FundamentalData, FundamentalScore

logger = logging.getLogger(__name__)

class DatabaseRepository:
    def __init__(self):
        self.pool = None
        self.db_url = os.getenv("DATABASE_URL", "postgresql://user:pass@db:5432/fundamentaldb")

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            logger.info("Database connected")
        except Exception as e:
            logger.error(f"Failed to connect to database at {self.db_url}: {e}")
            raise

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def get_cached_fundamental_data(self, ticker: str) -> FundamentalData | None:
        if not self.pool:
            return None
            
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT pe_ratio, pb_ratio, free_cash_flow, revenue_growth_yoy, profit_margin, debt_to_equity
                FROM fundamental_data_cache
                WHERE ticker = $1
            """, ticker)
            
            if row:
                return FundamentalData(
                    ticker=ticker,
                    pe_ratio=row['pe_ratio'],
                    pb_ratio=row['pb_ratio'],
                    free_cash_flow=row['free_cash_flow'],
                    revenue_growth_yoy=row['revenue_growth_yoy'],
                    profit_margin=row['profit_margin'],
                    debt_to_equity=row['debt_to_equity']
                )
            return None

    async def save_fundamental_data_cache(self, data: FundamentalData):
        if not self.pool:
            return
            
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO fundamental_data_cache 
                (ticker, pe_ratio, pb_ratio, free_cash_flow, revenue_growth_yoy, profit_margin, debt_to_equity, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                ON CONFLICT (ticker) DO UPDATE SET
                    pe_ratio = EXCLUDED.pe_ratio,
                    pb_ratio = EXCLUDED.pb_ratio,
                    free_cash_flow = EXCLUDED.free_cash_flow,
                    revenue_growth_yoy = EXCLUDED.revenue_growth_yoy,
                    profit_margin = EXCLUDED.profit_margin,
                    debt_to_equity = EXCLUDED.debt_to_equity,
                    updated_at = now()
            """, data.ticker, data.pe_ratio, data.pb_ratio, data.free_cash_flow, data.revenue_growth_yoy, data.profit_margin, data.debt_to_equity)

    async def save_assessment(self, score: FundamentalScore):
        if not self.pool:
            return
            
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO fundamental_assessments (ticker, intrinsic_value, moat_score, reasoning)
                VALUES ($1, $2, $3, $4)
            """, score.ticker, score.intrinsic_value, score.moat_score, score.reasoning)

db_repo = DatabaseRepository()
