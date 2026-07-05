from app.models.domain import FundamentalData
from app.infrastructure.database import db_repo
import random

async def fetch_fundamental_data(ticker: str) -> FundamentalData:
    # 1. Kiểm tra cache trong Database
    cached_data = await db_repo.get_cached_fundamental_data(ticker)
    if cached_data:
        return cached_data

    # 2. Nếu chưa có, tạo mock data
    seed_val = sum(ord(c) for c in ticker)
    random.seed(seed_val)
    
    data = FundamentalData(
        ticker=ticker,
        pe_ratio=round(random.uniform(5.0, 35.0), 2),
        pb_ratio=round(random.uniform(0.5, 5.0), 2),
        free_cash_flow=round(random.uniform(-10.0, 100.0), 2),
        revenue_growth_yoy=round(random.uniform(-20.0, 50.0), 2),
        profit_margin=round(random.uniform(2.0, 30.0), 2),
        debt_to_equity=round(random.uniform(0.1, 3.0), 2)
    )
    
    # 3. Lưu lại vào cache
    await db_repo.save_fundamental_data_cache(data)
    
    return data
