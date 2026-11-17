# Deployment Guide

## Local

```bash
cp .env.example .env
docker compose up --build
```

The API applies Alembic migrations on startup in local Compose. Production should run migrations as a separate release step.

## Kubernetes

Render base manifests:

```bash
kubectl apply -k infra/k8s/base
```

Render production overlay:

```bash
kubectl apply -k infra/k8s/overlays/production
```

## Production Recommendations

- Use managed PostgreSQL with pgvector enabled.
- Use managed Redis with TLS and eviction alerts.
- Use managed RabbitMQ or a cloud queue with dead-letter queues.
- Store secrets in AWS Secrets Manager, GCP Secret Manager, Vault, or External Secrets Operator.
- Put object artifacts in S3/GCS with server-side encryption.
- Run API, web, and worker images as separate deployment units.
- Use HPA for API CPU and worker queue depth.
- Terminate TLS at ingress and enforce HTTPS.
- Use blue-green or canary releases for API and web.
- Keep migrations backward compatible across rolling deployments.

## Rollback

1. Pause deploy automation.
2. Roll back web and API images.
3. Stop workers if the issue involves job mutation.
4. Apply a forward database migration if schema repair is needed.
5. Drain or replay affected RabbitMQ messages by idempotency key.
