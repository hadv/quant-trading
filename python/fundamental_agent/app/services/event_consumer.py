import asyncio
import logging
import json
from app.infrastructure.kafka_client import kafka_manager
from app.infrastructure.database import db_repo
from app.services.data_provider import fetch_fundamental_data
from app.core.llm_engine import llm_engine
from app.models.domain import DailyCandle

logger = logging.getLogger(__name__)

async def process_candle_event(payload: dict):
    try:
        # Extract candle data
        candle = DailyCandle(
            ticker=payload.get("Ticker", payload.get("ticker")),
            trade_date=payload.get("Date", payload.get("trade_date")),
            open_price=float(payload.get("Open", payload.get("open_price", 0))),
            high_price=float(payload.get("High", payload.get("high_price", 0))),
            low_price=float(payload.get("Low", payload.get("low_price", 0))),
            close_price=float(payload.get("Close", payload.get("close_price", 0))),
            volume=int(payload.get("Volume", payload.get("volume", 0)))
        )
        
        logger.info(f"Processing candle event for {candle.ticker} at {candle.trade_date}")
        
        # 1. Fetch Fundamental Data (Mocked for now)
        fundamental_data = await fetch_fundamental_data(candle.ticker)
        
        # 2. Analyze with LLM
        score = await llm_engine.analyze(fundamental_data, candle.close_price)
        logger.info(f"Analyzed fundamental score for {candle.ticker}: Intrinsic={score.intrinsic_value}, Moat={score.moat_score}")
        
        # 3. Save Assessment Locally
        await db_repo.save_assessment(score)
        
        # 4. Emit FundamentalScoreUpdated to Kafka
        event_payload = {
            "event_type": "FundamentalScoreUpdated",
            "aggregate_type": "Ticker",
            "aggregate_id": f"TICKER_{candle.ticker}",
            "payload": json.loads(score.model_dump_json())
        }
        await kafka_manager.publish_fundamental_score_event(event_payload)

    except Exception as e:
        logger.error(f"Error processing candle event: {e}", exc_info=True)

async def consume_events():
    if not kafka_manager.consumer:
        logger.error("Kafka consumer is not connected")
        return
        
    try:
        async for msg in kafka_manager.consumer:
            logger.info(f"Received message on topic {msg.topic}")
            payload = msg.value
            
            # The publisher might wrap this in {"event_type": "DailyCandleClosed", "payload": {...}}
            if isinstance(payload, dict):
                # We only process if it's a DailyCandleClosed event, or if it's the raw payload directly.
                event_type = payload.get("event_type")
                if event_type and event_type != "DailyCandleClosed":
                    continue # Ignore other events
                
                actual_payload = payload.get("payload", payload)
                if isinstance(actual_payload, str):
                    actual_payload = json.loads(actual_payload)
                    
                await process_candle_event(actual_payload)
    except Exception as e:
        logger.error(f"Kafka consumption error: {e}", exc_info=True)
