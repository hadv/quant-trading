import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/quantdb")
    MAX_ASSETS = int(os.getenv("MAX_ASSETS", "100"))
    NUM_SIMULATIONS = int(os.getenv("NUM_SIMULATIONS", "10000"))
    RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.05"))

config = Config()
