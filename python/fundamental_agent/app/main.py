from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
import logging

from app.infrastructure.kafka_client import kafka_manager
from app.infrastructure.database import db_repo
from app.services.event_consumer import consume_events
from app.core.rag.mock_data import mock_ingest_data

# Load environment variables (e.g. from .env file for local run)
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Fundamental Agent...")
    
    # We might want to wait a bit for Kafka to be ready in docker-compose
    await asyncio.sleep(5)
    
    # Ingest mock RAG data
    await mock_ingest_data()
    
    await db_repo.connect()
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

app = FastAPI(title="Fundamental Agent", lifespan=lifespan)

from app.telemetry import init_telemetry
init_telemetry(app, "fundamental-agent")

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "service": "fundamental_agent", 
        "kafka_producer": kafka_manager.producer is not None, 
        "kafka_consumer": kafka_manager.consumer is not None
    }
