import asyncio
import json
import signal
import uuid

import aio_pika
from prometheus_client import Counter, start_http_server
from sqlalchemy import select

from ai_workspace_api.core.config import get_settings
from ai_workspace_api.core.database import SessionLocal
from ai_workspace_api.core.logging import configure_logging, get_logger
from ai_workspace_api.core.models import JobRecord
from ai_workspace_api.infrastructure.distributed_lock import DistributedLock
from ai_workspace_api.modules.indexing.service import IndexingService

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

jobs_processed = Counter(
    "workspace_worker_jobs_processed_total",
    "Jobs processed",
    ["job_type", "status"],
)


async def handle_message(
    message: aio_pika.abc.AbstractIncomingMessage,
    redis_client: object | None = None,
) -> None:
    async with message.process(requeue=False):
        payload = json.loads(message.body.decode("utf-8"))
        job_type = payload["job_type"]
        idempotency_key = payload["idempotency_key"]
        job_payload = payload.get("payload", {})
        repository_id_str = job_payload.get("repository_id")

        async with SessionLocal() as session:
            job = await session.scalar(
                select(JobRecord).where(JobRecord.idempotency_key == idempotency_key)
            )

            # 1. Deduplicate: if job already succeeded, skip redundant execution
            if job is not None and job.status == "succeeded":
                logger.info("worker.job_already_succeeded", idempotency_key=idempotency_key)
                return

            lock = (
                DistributedLock(
                    redis_client,  # type: ignore[arg-type]
                    f"lock:indexing:{repository_id_str}",
                    ttl_seconds=300,
                )
                if repository_id_str and redis_client is not None
                else None
            )

            # 2. Check if job is currently running
            if job is not None and job.status == "running":
                if lock is not None and await lock.is_locked():
                    logger.warning("worker.job_already_running", idempotency_key=idempotency_key)
                    return
                logger.info("worker.recovering_interrupted_job", idempotency_key=idempotency_key)
                job.attempts += 1
            elif job is None:
                job = JobRecord(
                    job_type=job_type,
                    status="running",
                    idempotency_key=idempotency_key,
                    payload=job_payload,
                    attempts=1,
                )
                session.add(job)
            else:
                job.status = "running"
                job.attempts += 1

            if lock is not None:
                acquired = await lock.acquire()
                if not acquired:
                    logger.warning(
                        "worker.repo_lock_contention",
                        repository_id=repository_id_str,
                        idempotency_key=idempotency_key,
                    )
                    return

            try:
                if job_type == "repository.index":
                    repository_id = uuid.UUID(repository_id_str)
                    await IndexingService(session, settings).index_repository(repository_id)
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
                if lock is not None:
                    await lock.release()


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
