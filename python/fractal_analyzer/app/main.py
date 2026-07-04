from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
import logging

from app.infrastructure.database import db_repo
from app.infrastructure.kafka_client import kafka_manager
from app.services.event_consumer import consume_events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Fractal Analyzer Agent...")
    await db_repo.connect()
    
    # We might want to wait a bit for Kafka to be ready in docker-compose
    await asyncio.sleep(5)
    
    await kafka_manager.connect_producer()
    await kafka_manager.connect_consumer()
    
    # Start consumer loop
    consumer_task = asyncio.create_task(consume_events())
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    consumer_task.cancel()
    await kafka_manager.stop()
    await db_repo.close()

app = FastAPI(title="Fractal Analyzer Agent", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "fractal_analyzer", "kafka_producer": kafka_manager.producer is not None, "kafka_consumer": kafka_manager.consumer is not None}
