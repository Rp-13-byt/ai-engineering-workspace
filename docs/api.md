# API Documentation

FastAPI exposes the live OpenAPI specification at `/api/v1/openapi.json` and Swagger UI at `/api/docs`.

## API Principles

- Versioned REST paths under `/api/v1`.
- JSON request and response bodies.
- Pydantic validation on every write path.
- Organization scoping through `X-Organization-Id`.
- Bearer JWT authentication.
- Permission checks through RBAC dependencies.
- Pagination through `limit` and `offset`.
- Structured errors with request IDs.

## Endpoint Inventory

| Area | Method | Path | Purpose |
| --- | --- | --- | --- |
| Auth | POST | `/api/v1/auth/signup` | Create user, organization, owner membership, tokens |
| Auth | POST | `/api/v1/auth/login` | Password login |
| Auth | POST | `/api/v1/auth/refresh` | Rotate refresh session and issue access token |
| Auth | POST | `/api/v1/auth/logout` | Revoke refresh session |
| Auth | GET | `/api/v1/auth/github/url` | Start GitHub OAuth |
| Auth | POST | `/api/v1/auth/github/callback` | OAuth callback boundary |
| Users | GET | `/api/v1/users/me` | Current user and memberships |
| Repositories | POST | `/api/v1/repositories/import` | Import GitHub repository and enqueue indexing |
| Repositories | GET | `/api/v1/repositories` | List repositories |
| Repositories | GET | `/api/v1/repositories/{id}` | Repository detail |
| Repositories | POST | `/api/v1/repositories/{id}/reindex` | Queue reindex |
| Indexing | GET | `/api/v1/indexing/{repository_id}` | Indexing status |
| Search | POST | `/api/v1/search/semantic` | Vector search over indexed chunks |
| Chat | POST | `/api/v1/chat` | Retrieval-augmented AI code chat |
| Pull requests | POST | `/api/v1/pull-requests/generate` | Generate PR draft or open PR |
| Tasks | GET | `/api/v1/tasks` | List tasks |
| Tasks | POST | `/api/v1/tasks` | Create task |
| Tasks | PATCH | `/api/v1/tasks/{id}` | Update task |
| Docs | POST | `/api/v1/docs/generate` | Generate markdown docs |
| Docs | POST | `/api/v1/docs/tests` | Generate test plan |
| Docs | POST | `/api/v1/docs/bugs` | Detect bug candidates |
| Realtime | WS | `/ws/{organization_id}` | Presence, heartbeat, live task events |
| Health | GET | `/health` | Liveness |
| Health | GET | `/ready` | Database and Redis readiness |

## Error Shape

```json
{
  "error": "Repository not found",
  "request_id": "2b97a6de-6ac5-43a6-9f63-4d7bdb4fda29"
}
```

## OpenAPI Generation

After the API is running:

```bash
make openapi
```

This writes `docs/openapi.json`.
