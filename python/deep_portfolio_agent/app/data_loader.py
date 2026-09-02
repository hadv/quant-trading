import pandas as pd
from sqlalchemy import create_engine
from app.config import config

class DataLoader:
    def __init__(self):
        self.engine = create_engine(config.DATABASE_URL)

    def load_top_100_assets(self) -> list:
        # Mocking or querying the fundamental_agent's result table
        # Example query if we had a table `fundamental_scores`
        # query = "SELECT symbol FROM fundamental_scores ORDER BY moat_score DESC LIMIT 100"
        # For now, returning dummy data
        print("Mock: Loading top assets from Database...")
        return [f"ASSET_{i}" for i in range(1, config.MAX_ASSETS + 1)]

    def load_historical_candles(self, symbols: list) -> pd.DataFrame:
        """
        Query historical OHLCV candles from the Postgres DB.
        """
        # query = f"SELECT symbol, close_time, close_price FROM daily_candles WHERE symbol IN {tuple(symbols)}"
        # df = pd.read_sql(query, self.engine)
        print(f"Mock: Loading historical candles for {len(symbols)} assets...")
        
        # Mock dataframe for demonstration
        import numpy as np
        dates = pd.date_range(start='2025-01-01', periods=100)
        data = {sym: np.random.lognormal(0, 0.02, 100).cumprod() * 100 for sym in symbols}
        df = pd.DataFrame(data, index=dates)
        return df

    def calculate_returns_and_covariance(self, df: pd.DataFrame):
        """
        Returns expected returns and covariance matrix which are needed for JAX SDE.
        """
        returns = df.pct_change().dropna()
        mean_returns = returns.mean().values
        cov_matrix = returns.cov().values
        return mean_returns, cov_matrix
