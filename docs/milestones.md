# Milestones and Senior-Engineer Review Notes

## 1. Architecture and Repository Structure

Design decisions:
- Monorepo with separate deployable apps for API, web, and worker.
- Clean architecture boundaries preserve a migration path to microservices.
- PostgreSQL + pgvector chosen as the initial vector store to simplify transactional consistency.

Trade-offs:
- pgvector is operationally simpler than a separate vector database, but a dedicated search engine may outperform it at very high vector counts.
- Modular monolith is faster to develop than microservices and avoids premature distributed transactions.

Interview questions:
- When would you split a modular monolith into services?
- How do you prevent distributed systems complexity from leaking into product code?
- What is the difference between horizontal and vertical scaling?

10M-user scalability:
- Split read and write workloads.
- Introduce repository-indexing shards by organization or repository ID.
- Move vector search to a dedicated ANN platform when index size dominates PostgreSQL memory.

Potential bottlenecks:
- Database connection saturation.
- Queue lag during large repository imports.
- LLM provider latency and rate limits.

Complexity:
- API routing is O(1) by route lookup.
- Repository indexing is O(F + C * E), where F is files, C is chunks, and E is embedding cost.

Big-tech version:
- Google or Meta would likely use internal Borg/Kubernetes schedulers, global RPC systems, centralized identity, and separate search/indexing services with multi-region replication.

## 2. Database, Auth, and Core API

Design decisions:
- Async SQLAlchemy with explicit session lifecycle.
- JWT access tokens plus rotating refresh-token sessions.
- RBAC enforced through organization memberships and permission mapping.

Trade-offs:
- JWTs reduce database lookups on every request but require careful revocation strategy.
- Refresh-token sessions add state but make logout, device tracking, and compromise response practical.

Interview questions:
- How do you design token revocation for JWT systems?
- What indexes would you add for multi-tenant access checks?
- How do you protect a login endpoint from brute-force attacks?

10M-user scalability:
- Cache membership lookups in Redis.
- Partition audit logs by time.
- Use read replicas for dashboard and activity feeds.

Potential bottlenecks:
- Hot organization membership rows.
- Unbounded audit-log writes.
- Password hashing CPU under credential-stuffing attacks.

Complexity:
- Login user lookup is O(log N) with an email index.
- Permission check is O(1) from cache or O(log M) with a compound membership index.

Big-tech version:
- Amazon-style systems would use centralized IAM concepts, policy evaluation services, hardware-backed secret storage, and risk-based authentication signals.

## 3. Repository Import, Indexing, Search, and AI

Design decisions:
- Repository import is asynchronous and idempotent.
- Chunks store metadata, text, hashes, and embeddings for selective re-indexing.
- LLM provider access goes through a provider-agnostic gateway.

Trade-offs:
- Chunk-level indexing increases storage use but enables precise retrieval.
- Provider abstraction adds code but prevents lock-in and makes testing easier.

Interview questions:
- How do HNSW indexes work?
- How would you chunk source code for retrieval?
- How do you avoid prompt injection when using repository content?

10M-user scalability:
- Content-address chunks and deduplicate across forks.
- Use batching and backpressure for embedding jobs.
- Add regional vector indexes and async replication.

Potential bottlenecks:
- GitHub API rate limits.
- Embedding throughput.
- Vector-index memory pressure.

Complexity:
- Semantic search is approximately O(log N) with ANN indexing, plus O(K) reranking.
- Diff generation is O(C + D), where C is retrieved context size and D is generated diff size.

Big-tech version:
- Meta-scale systems would separate code graph indexing, embedding pipelines, feature stores, and online retrieval services.

## 4. Frontend and Real-Time Collaboration

Design decisions:
- Next.js app router with React Query for server state and Zustand for local workspace state.
- WebSocket presence and notifications prevent polling.
- Forms use React Hook Form and Zod for typed validation.

Trade-offs:
- React Query adds a cache layer that must be invalidated carefully.
- WebSockets add connection-management complexity but lower latency for collaboration.

Interview questions:
- What state belongs in React Query versus Zustand?
- How do you design reconnect and heartbeat logic?
- How would you make a dashboard accessible by keyboard?

10M-user scalability:
- Use regional WebSocket gateways.
- Move presence to Redis Cluster or a dedicated pub/sub fabric.
- Use edge caching for static assets and code previews.

Potential bottlenecks:
- WebSocket fanout.
- Oversized client bundles.
- Inefficient list rendering for large search results.

Complexity:
- Presence updates are O(1) per connection and O(R) for room fanout.
- Infinite scrolling fetches O(P) page payload per request.

Big-tech version:
- Netflix or Google would likely use edge-deployed frontends, streaming updates, strict performance budgets, and experiment-driven UI rollout.

## 5. Workers, Observability, Deployment, and Tests

Design decisions:
- RabbitMQ handles durable work dispatch and dead-letter routing.
- Prometheus scrapes API and worker metrics.
- Docker Compose mirrors production dependencies; Kubernetes manifests define scalable deployment units.

Trade-offs:
- RabbitMQ offers strong queue semantics but adds one more stateful dependency.
- Docker Compose is excellent for local parity but not a production orchestrator.

Interview questions:
- How do retries differ from idempotency?
- What metrics prove an indexing pipeline is healthy?
- How do readiness and liveness probes differ?

10M-user scalability:
- Use autoscaled worker pools partitioned by job type.
- Add queue priority classes for interactive versus batch work.
- Use multi-region deployment with database failover.

Potential bottlenecks:
- Dead-letter queue growth.
- Slow CI pipelines.
- Missing cardinality controls in metrics labels.

Complexity:
- Queue enqueue is O(1).
- Worker throughput is O(W * B / L), where W is worker count, B is batch size, and L is average job latency.

Big-tech version:
- Amazon would use managed queueing, centralized observability, automated rollback, cell-based architecture, and strict service-level objectives.

## Phase 1 Critical Fixes - 2026-06-07

Completed:
- Added repository ownership checks before repository-scoped chat, search, documentation, pull request, and indexing-status operations.
- Added conversation scoping so a chat request cannot attach to another repository or another user's conversation.
- Added WebSocket membership validation before joining an organization room.
- Fixed worker job tracking to update job records by idempotency key and increment attempts.
- Replaced fragile passlib password hashing with bcrypt-SHA256 hashing while preserving verification for existing bcrypt hashes.

Compatibility:
- No request or response schema changes were introduced.
- Existing route paths and headers remain unchanged.
- Existing bcrypt password hashes remain verifiable.

Verification:
- Backend tests: 13 passed.
- Touched-file syntax/import/line-length lint subset: passed.

Remaining risks:
- Full Ruff still reports existing repository-wide policy issues, especially FastAPI `Depends(...)` defaults under rule B008.
- Frontend tests require local npm dependencies before they can run.
- Repository ingestion and AI/RAG behavior are still Phase 2 and Phase 3 work.
