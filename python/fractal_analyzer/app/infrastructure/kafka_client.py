from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.core.config import settings
import json
import logging

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self):
        self.producer = None
        self.consumer = None

    async def connect_producer(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka Producer connected")

    async def connect_consumer(self):
        self.consumer = AIOKafkaConsumer(
            settings.KAFKA_INPUT_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.CONSUMER_GROUP,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset="earliest"
        )
        await self.consumer.start()
        logger.info("Kafka Consumer connected")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()

    async def publish_risk_event(self, payload: dict):
        if self.producer:
            await self.producer.send_and_wait(settings.KAFKA_OUTPUT_TOPIC, payload)

kafka_manager = KafkaManager()
