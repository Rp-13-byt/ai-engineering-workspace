# Database Design

PostgreSQL is the source of truth. pgvector stores embeddings for code chunks so repository metadata, chunk metadata, and vector indexes stay transactionally aligned during the first stage of scale.

## Core Tables

- `users`: account identity and verification state.
- `organizations`: tenant boundary.
- `memberships`: user-to-organization RBAC.
- `sessions`: hashed refresh tokens with expiry and revocation.
- `oauth_accounts`: GitHub identity and token boundary.
- `repositories`: imported repository metadata.
- `code_documents`: indexed files by path and commit.
- `code_chunks`: chunk content and vector embeddings.
- `conversations` and `messages`: AI chat history and citations.
- `pull_requests`: generated PR drafts and GitHub URLs.
- `workspace_tasks`: task tracking.
- `audit_logs`: security and compliance trail.
- `job_records`: idempotent background jobs.

## Indexes and Optimization

- Unique tenant repository identity: `(organization_id, provider, owner, name)`.
- Membership permission checks: `(organization_id, role)` and unique `(user_id, organization_id)`.
- Session lookup: `token_hash`.
- Repository filtering: `(organization_id, indexing_status)`.
- Code filtering: `(repository_id, language)`.
- Vector search: HNSW index on `code_chunks.embedding` with cosine distance.
- Task board queries: `(repository_id, status, priority)`.
- Audit trails: `(organization_id, created_at)` and `(actor_id, created_at)`.

## ER Diagram

See [Architecture](architecture.md) for the Mermaid ER diagram.

## Scaling Plan

- Partition `audit_logs` and `messages` by time.
- Partition or shard code chunks by organization or repository ID.
- Add read replicas for dashboard and reporting queries.
- Move embeddings to a dedicated ANN service when vector memory or recall tuning dominates database operations.
- Use content-addressed chunk deduplication for forks and monorepos.
