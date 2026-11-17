# Monitoring

## Metrics

- API metrics are exposed at `/metrics`.
- Worker metrics are exposed on port `9100`.
- Prometheus scrapes both in Docker Compose.
- Grafana is preconfigured with a Prometheus datasource.

## Key Signals

- API request rate, latency, and error rate.
- Database pool saturation and query latency.
- Redis latency and eviction count.
- RabbitMQ queue depth, consumer count, retry rate, and dead-letter count.
- Worker job success/failure totals.
- Repository indexing duration and chunks per second.
- LLM latency, token usage, provider errors, and rate-limit responses.

## Alert Ideas

- API p95 latency above SLO for 10 minutes.
- Queue depth growing while workers are healthy.
- Dead-letter queue has any messages.
- PostgreSQL connections above 80 percent.
- Redis memory above 80 percent.
- LLM provider error rate above 5 percent.
