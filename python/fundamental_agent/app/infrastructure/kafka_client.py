import os
import json
import logging
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BROKERS", "localhost:9092")
        self.consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "fundamental_agent_group")
        self.topic_in = os.getenv("KAFKA_TOPIC_IN", "market.events")
        self.topic_out = os.getenv("KAFKA_TOPIC_OUT", "analysis.events")
        
        self.consumer = None
        self.producer = None

    async def connect_producer(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info(f"Connected to Kafka Producer at {self.bootstrap_servers}")

    async def connect_consumer(self):
        self.consumer = AIOKafkaConsumer(
            self.topic_in,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            auto_offset_reset="earliest"
        )
        await self.consumer.start()
        logger.info(f"Connected to Kafka Consumer at {self.bootstrap_servers}, listening to {self.topic_in}")

    async def publish_fundamental_score_event(self, event_payload: dict):
        if not self.producer:
            logger.error("Producer is not initialized.")
            return
        try:
            await self.producer.send_and_wait(self.topic_out, event_payload)
            logger.info(f"Published FundamentalScoreUpdated event to {self.topic_out}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

kafka_manager = KafkaManager()
