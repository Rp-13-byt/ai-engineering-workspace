# Developer Guide

## Backend

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install ".[dev]"
alembic upgrade head
uvicorn ai_workspace_api.main:app --reload
```

## Frontend

```bash
cd apps/web
npm install
npm run dev
```

## Testing

```bash
make test-api
make test-web
```

## Code Organization

- `core`: settings, database, security, permissions, telemetry.
- `infrastructure`: GitHub, LLM, queue, vector store, object storage adapters.
- `modules`: feature-oriented API routes, schemas, and services.
- `workers`: queue consumers and background job execution.

## Adding a Feature

1. Add schema models in the feature module.
2. Add service logic without transport assumptions.
3. Add route handlers that validate and authorize.
4. Add tests around service rules and API behavior.
5. Add migration/indexes if data shape changes.
6. Update docs and OpenAPI.
