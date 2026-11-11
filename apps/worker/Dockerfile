FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential git \
  && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic
COPY apps/api/src ./src

ENV PYTHONPATH=/app/src

EXPOSE 9100
CMD ["python", "-m", "ai_workspace_api.workers.main"]
