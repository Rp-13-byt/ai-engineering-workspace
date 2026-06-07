import asyncio
import json
import signal
import uuid

import aio_pika
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from sqlalchemy import select

from ai_workspace_api.core.config import get_settings
from ai_workspace_api.core.database import SessionLocal
from ai_workspace_api.core.logging import configure_logging, get_logger
from ai_workspace_api.core.models import JobRecord
from ai_workspace_api.modules.indexing.service import IndexingService

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

jobs_processed = Counter(
    "workspace_worker_jobs_processed_total",
    "Jobs processed",
    ["job_type", "status"],
)
WORKER_ACTIVE_JOBS = Gauge(
    "workspace_worker_active_jobs",
    "Number of currently active jobs",
)
WORKER_JOB_DURATION = Histogram(
    "workspace_worker_job_duration_seconds",
    "Time taken to process a job",
    ["job_type"],
    buckets=[1, 5, 15, 60, 300, 900, 3600],
)


async def handle_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process(requeue=False):
        WORKER_ACTIVE_JOBS.inc()
        payload = json.loads(message.body.decode("utf-8"))
        job_type = payload["job_type"]
        idempotency_key = payload["idempotency_key"]
        with WORKER_JOB_DURATION.labels(job_type=job_type).time():
            async with SessionLocal() as session:
                job = await session.scalar(
                    select(JobRecord).where(JobRecord.idempotency_key == idempotency_key)
                )
                if job is None:
                    job = JobRecord(
                        job_type=job_type,
                        status="running",
                        idempotency_key=idempotency_key,
                        payload=payload.get("payload", {}),
                        attempts=1,
                    )
                    session.add(job)
                else:
                    job.status = "running"
                    job.attempts += 1
                try:
                    if job_type == "repository.index":
                        repository_id = uuid.UUID(payload["payload"]["repository_id"])
                        import redis.asyncio as aioredis
                        redis_client = aioredis.from_url(settings.redis_url)
                        lock = redis_client.lock(f"lock:repo_index:{repository_id}", timeout=1800, blocking_timeout=2)
                        if not await lock.acquire():
                            logger.warning("Job skipped, indexing lock already held", repository_id=str(repository_id))
                            raise RuntimeError("Concurrent indexing lock held")
                        try:
                            await IndexingService(session, settings).index_repository(repository_id)
                        finally:
                            await lock.release()
                            await redis_client.aclose()
                    else:
                        raise ValueError(f"Unsupported job type: {job_type}")
                    job.status = "succeeded"
                    job.last_error = None
                    await session.commit()
                    jobs_processed.labels(job_type=job_type, status="succeeded").inc()
                except Exception as exc:
                    job.status = "failed"
                    job.last_error = str(exc)
                    await session.commit()
                    jobs_processed.labels(job_type=job_type, status="failed").inc()
                    logger.exception("worker.job_failed", job_type=job_type)
                    raise
                finally:
                    WORKER_ACTIVE_JOBS.dec()


async def run_worker() -> None:
    start_http_server(9100)
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=4)
    await channel.declare_exchange("workspace.jobs", aio_pika.ExchangeType.TOPIC, durable=True)
    await channel.declare_exchange("workspace.jobs.dlx", aio_pika.ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue(
        "workspace.jobs.indexing",
        durable=True,
        arguments={"x-dead-letter-exchange": "workspace.jobs.dlx"},
    )
    await queue.bind("workspace.jobs", routing_key="repository.index")
    await queue.consume(handle_message)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    logger.info("worker.started")
    await stop_event.wait()
    await connection.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
