.PHONY: dev down migrate test-api test-web lint-api lint-web openapi

dev:
	docker compose up --build

down:
	docker compose down --remove-orphans

migrate:
	docker compose run --rm api alembic upgrade head

test-api:
	cd apps/api && python -m pytest

test-web:
	cd apps/web && npm test

lint-api:
	cd apps/api && ruff check src tests && mypy src

lint-web:
	cd apps/web && npm run lint

openapi:
	curl http://localhost:8000/api/v1/openapi.json -o docs/openapi.json
