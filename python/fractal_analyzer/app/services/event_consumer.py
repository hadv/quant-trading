import asyncio
import logging
from app.infrastructure.kafka_client import kafka_manager
from app.infrastructure.database import db_repo
from app.core.engine import analyze_fractal_risk
from app.models.domain import DailyCandle
import json

logger = logging.getLogger(__name__)

async def process_candle_event(payload: dict):
    try:
        # Assuming payload contains the full candle info when published by the Go service
        # If the Go service only publishes {"Ticker": "BTC", "Date": ...} we might need to fetch data.
        # Here we assume the Go service publishes a comprehensive DailyCandle payload.
        # Alternatively, we just extract ticker, trade_date, open, high, low, close, volume.
        candle = DailyCandle(
            ticker=payload.get("Ticker", payload.get("ticker")),
            trade_date=payload.get("Date", payload.get("trade_date")),
            open_price=float(payload.get("Open", payload.get("open_price", 0))),
            high_price=float(payload.get("High", payload.get("high_price", 0))),
            low_price=float(payload.get("Low", payload.get("low_price", 0))),
            close_price=float(payload.get("Close", payload.get("close_price", 0))),
            volume=int(payload.get("Volume", payload.get("volume", 0)))
        )
        
        # 1. Save candle locally
        await db_repo.save_candle(candle)
        
        # 2. Fetch history
        prices = await db_repo.get_historical_prices(candle.ticker)
        
        # 3. Analyze Risk
        risk = analyze_fractal_risk(candle.ticker, prices)
        logger.info(f"Analyzed risk for {candle.ticker}: {risk.regime} (H={risk.hurst_exponent:.4f})")
        
        # 4. Save Assessment Locally
        await db_repo.save_assessment(risk)
        
        # 5. Emit Risk Assessment to Kafka
        event_payload = {
            "event_type": "FractalRiskAssessed",
            "aggregate_type": "Ticker",
            "aggregate_id": f"TICKER_{candle.ticker}",
            "payload": json.loads(risk.model_dump_json())
        }
        await kafka_manager.publish_risk_event(event_payload)

    except Exception as e:
        logger.error(f"Error processing candle event: {e}")

async def consume_events():
    if not kafka_manager.consumer:
        logger.error("Kafka consumer is not connected")
        return
        
    try:
        async for msg in kafka_manager.consumer:
            logger.info(f"Received message on topic {msg.topic}")
            payload = msg.value
            
            # The Go outbox publisher might wrap this in {"event_type": "DailyCandleClosed", "payload": {...}}
            # Let's extract the actual candle data
            if isinstance(payload, dict):
                actual_payload = payload.get("payload", payload)
                if isinstance(actual_payload, str):
                    actual_payload = json.loads(actual_payload)
                    
                await process_candle_event(actual_payload)
    except Exception as e:
        logger.error(f"Kafka consumption error: {e}")
