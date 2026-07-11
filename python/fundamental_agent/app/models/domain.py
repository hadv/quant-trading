from pydantic import BaseModel, Field
from typing import Optional

class DailyCandle(BaseModel):
    ticker: str
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int

class FundamentalData(BaseModel):
    ticker: str
    pe_ratio: float = Field(..., description="Price to Earnings ratio")
    pb_ratio: float = Field(..., description="Price to Book ratio")
    free_cash_flow: float = Field(..., description="Free cash flow in billions")
    revenue_growth_yoy: float = Field(..., description="Revenue growth year over year in percentage")
    profit_margin: float = Field(..., description="Net profit margin in percentage")
    debt_to_equity: float = Field(..., description="Debt to Equity ratio")

class FundamentalScore(BaseModel):
    ticker: str
    intrinsic_value: float = Field(..., description="Estimated intrinsic value per share")
    moat_score: int = Field(..., ge=1, le=10, description="Economic moat score from 1 to 10")
    reasoning: str = Field(..., description="Reasoning behind the assessment")

class DCFResult(BaseModel):
    intrinsic_value: float = Field(..., description="Estimated intrinsic value per share calculated via DCF logic")
    dcf_reasoning: str = Field(..., description="Explanation of the math and assumptions used for the intrinsic value")

class MoatResult(BaseModel):
    moat_score: int = Field(..., ge=1, le=10, description="Economic moat score from 1 to 10")
    moat_reasoning: str = Field(..., description="Explanation of the competitive advantage assessment based on qualitative data")
