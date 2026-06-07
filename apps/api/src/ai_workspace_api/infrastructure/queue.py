import json
from dataclasses import dataclass
from typing import Any

import aio_pika

from ai_workspace_api.core.config import Settings


@dataclass(frozen=True)
class JobMessage:
    job_type: str
    payload: dict[str, Any]
    idempotency_key: str


class QueuePublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def publish(self, routing_key: str, message: JobMessage) -> None:
        connection = await aio_pika.connect_robust(self.settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange("workspace.jobs", aio_pika.ExchangeType.TOPIC, durable=True)
            await channel.declare_queue(
                "workspace.jobs.indexing",
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "workspace.jobs.dlx",
                    "x-message-ttl": 300000,
                },
            )
            body = json.dumps(
                {
                    "job_type": message.job_type,
                    "payload": message.payload,
                    "idempotency_key": message.idempotency_key,
                }
            ).encode("utf-8")
            await exchange.publish(
                aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=routing_key,
            )
