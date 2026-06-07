# Architecture

This project is a production-style AI software engineering workspace. It is a modular monorepo designed to run locally with Docker Compose and to deploy to Kubernetes without changing application code.

## High-Level System

```mermaid
flowchart LR
  Browser["Next.js web app"] --> Edge["Nginx / ingress"]
  Edge --> API["FastAPI REST API"]
  Edge --> WS["FastAPI WebSockets"]
  API --> PG[("PostgreSQL + pgvector")]
  API --> Redis[("Redis cache")]
  API --> Rabbit["RabbitMQ"]
  API --> S3[("S3-compatible object storage")]
  API --> GitHub["GitHub API"]
  API --> LLM["OpenAI / Gemini"]
  Rabbit --> Worker["Background workers"]
  Worker --> PG
  Worker --> Redis
  Worker --> S3
  Worker --> GitHub
  Worker --> LLM
  API --> Metrics["Prometheus metrics"]
  Worker --> Metrics
  Metrics --> Grafana["Grafana dashboards"]
```

## Why This Architecture Impresses Senior Reviewers

- The API is stateless and horizontally scalable; all durable state lives in PostgreSQL, Redis, RabbitMQ, and object storage.
- Repository indexing runs asynchronously through RabbitMQ so user-facing requests are low latency and resilient to LLM or GitHub slowness.
- PostgreSQL with pgvector is selected as the first vector database because it keeps transactional metadata and embeddings close together. At high scale, the same repository abstraction can move to a dedicated vector system such as Milvus, Vespa, or Pinecone.
- Redis is used only for hot-path cache, rate limiting, realtime presence, and idempotency keys; it is not the source of truth.
- Module boundaries mirror likely future services: auth, repositories, indexing, search, chat, pull requests, tasks, docs, realtime, and workers.
- Observability is a first-class concern: structured logs, health checks, readiness probes, Prometheus metrics, and trace-friendly request IDs.

## Request Flow

```mermaid
sequenceDiagram
  participant U as User
  participant W as Next.js
  participant A as FastAPI
  participant R as Redis
  participant P as PostgreSQL
  participant Q as RabbitMQ
  participant B as Worker
  participant G as GitHub
  participant L as LLM

  U->>W: Import repository
  W->>A: POST /api/v1/repositories/import
  A->>G: Validate repository access
  A->>P: Persist repository metadata
  A->>Q: Publish indexing job
  A-->>W: 202 Accepted
  B->>Q: Consume job
  B->>G: Fetch repository tree
  B->>L: Generate embeddings and summaries
  B->>P: Store chunks and vectors
  B->>R: Invalidate search cache
  B-->>W: WebSocket notification
```

## Clean Architecture Layers

```mermaid
flowchart TB
  Routes["API routes and WebSocket handlers"]
  Schemas["Pydantic schemas"]
  Services["Application services / use cases"]
  Domain["Domain policies and entities"]
  Infra["Infrastructure adapters"]
  Data["Database, cache, queue, object storage, APIs"]

  Routes --> Schemas
  Routes --> Services
  Services --> Domain
  Services --> Infra
  Infra --> Data
```

Routes validate transport concerns only. Services own business rules. Infrastructure adapters isolate GitHub, LLM providers, queueing, storage, cache, and vector search. This makes the system testable and leaves a path to extract services later.

## Data Model

```mermaid
erDiagram
  organizations ||--o{ memberships : has
  users ||--o{ memberships : joins
  users ||--o{ sessions : owns
  users ||--o{ audit_logs : creates
  organizations ||--o{ repositories : owns
  repositories ||--o{ code_documents : contains
  code_documents ||--o{ code_chunks : splits
  repositories ||--o{ conversations : discusses
  conversations ||--o{ messages : contains
  repositories ||--o{ pull_requests : generates
  repositories ||--o{ workspace_tasks : tracks
  users ||--o{ workspace_tasks : assigned

  users {
    uuid id PK
    string email UK
    string password_hash
    string display_name
    bool is_verified
    timestamptz created_at
  }

  organizations {
    uuid id PK
    string slug UK
    string name
    timestamptz created_at
  }

  memberships {
    uuid id PK
    uuid user_id FK
    uuid organization_id FK
    string role
  }

  repositories {
    uuid id PK
    uuid organization_id FK
    string provider
    string owner
    string name
    string default_branch
    string indexing_status
  }

  code_chunks {
    uuid id PK
    uuid document_id FK
    int start_line
    int end_line
    text content
    vector embedding
  }
```

## Low-Latency Choices

- Auth and organization permissions are cached with short TTLs and invalidated on membership changes.
- Search uses pgvector HNSW indexes for approximate nearest neighbor queries.
- Long-running operations return `202 Accepted` and publish worker jobs.
- WebSocket channels carry job progress and presence without polling.
- API pagination uses keyset-friendly IDs and indexed timestamp columns.

