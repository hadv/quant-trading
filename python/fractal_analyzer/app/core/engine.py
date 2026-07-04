import logging
from datetime import datetime, timezone
import numpy as np
from hurst import compute_Hc
from app.models.domain import FractalRisk
from app.core.config import settings

logger = logging.getLogger(__name__)

def analyze_fractal_risk(ticker: str, prices: list[float]) -> FractalRisk:
    if len(prices) < settings.MIN_DATA_POINTS:
        return FractalRisk(
            ticker=ticker,
            hurst_exponent=0.5,
            fractal_dimension=1.5,
            risk_level=0.0,
            regime="insufficient_data",
            timestamp=datetime.now(timezone.utc),
        )

    series = np.array(prices)
    try:
        H, _, _ = compute_Hc(series, kind='price', simplified=True)
    except Exception as e:
        logger.error(f"Error computing Hurst for {ticker}: {e}")
        H = 0.5
    
    fractal_dimension = 2.0 - H
    risk_level = abs(H - 0.5) * 2.0
    
    if H < 0.4:
        regime = "chaotic_anti_persistent"
    elif H > 0.6:
        regime = "trending_persistent"
    else:
        regime = "random_walk"

    return FractalRisk(
        ticker=ticker,
        hurst_exponent=H,
        fractal_dimension=fractal_dimension,
        risk_level=min(1.0, risk_level),
        regime=regime,
        timestamp=datetime.now(timezone.utc),
    )
