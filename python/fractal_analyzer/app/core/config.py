from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:pass@db:5432/fractaldb"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_INPUT_TOPIC: str = "quant.events.candles"
    KAFKA_OUTPUT_TOPIC: str = "quant.events.fractalrisk"
    CONSUMER_GROUP: str = "fractal_analyzer_group"
    MIN_DATA_POINTS: int = 50

    class Config:
        env_file = ".env"

settings = Settings()
