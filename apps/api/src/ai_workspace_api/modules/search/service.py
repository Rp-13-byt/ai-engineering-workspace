import json
import re
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.logging import get_logger
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.llm import LLMGateway, RetrievedContext
from ai_workspace_api.infrastructure.vector_store import VectorStore, reciprocal_rank_fusion
from ai_workspace_api.modules.search.schemas import SearchRequest, SearchResponse, SearchResult

logger = get_logger(__name__)

# Identifier heuristic: single word with valid identifier characters
IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$.-]*$")


class SearchService:
    def __init__(self, session: AsyncSession, redis: Redis | None, settings: Settings) -> None:
        self.session = session
        self.redis = redis
        self.settings = settings
        self.llm = LLMGateway(settings, redis=redis)
        self.vector_store = VectorStore(session)

    async def semantic_search(
        self,
        payload: SearchRequest,
        organization_id: uuid.UUID,
    ) -> SearchResponse:
        repository = await get_repository_for_organization(self.session, organization_id, payload.repository_id)

        index_version = repository.last_indexed_commit or "initial"
        embedding_model = repository.embedding_model or self.settings.embedding_model
        cache_key = f"search:semantic:{payload.repository_id}:{index_version}:{embedding_model}:{payload.limit}:{payload.query}"

        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    return SearchResponse(
                        results=[SearchResult(**item) for item in json.loads(cached)],
                        cached=True,
                    )
            except Exception as exc:
                logger.warning("search_service.cache_read_failed", error=str(exc))

        embedding = (await self.llm.embed([payload.query]))[0]
        contexts = await self.vector_store.semantic_search(
            payload.repository_id,
            embedding,
            limit=payload.limit,
            embedding_model=embedding_model,
        )
        results = [self._context_to_result(ctx) for ctx in contexts]

        if self.redis is not None:
            try:
                await self.redis.setex(cache_key, 60, json.dumps([item.model_dump() for item in results]))
            except Exception as exc:
                logger.warning("search_service.cache_write_failed", error=str(exc))

        return SearchResponse(results=results, cached=False)

    async def hybrid_search(
        self,
        payload: SearchRequest,
        organization_id: uuid.UUID,
    ) -> SearchResponse:
        """Combine semantic vector search, PostgreSQL full-text search, and exact symbol lookup via RRF."""
        repository = await get_repository_for_organization(self.session, organization_id, payload.repository_id)

        index_version = repository.last_indexed_commit or "initial"
        embedding_model = repository.embedding_model or self.settings.embedding_model
        exact_symbol = payload.exact_symbol or ""
        cache_key = (
            f"search:hybrid:{payload.repository_id}:{index_version}:{embedding_model}:"
            f"{payload.limit}:{payload.query}:{exact_symbol}"
        )

        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    return SearchResponse(
                        results=[SearchResult(**item) for item in json.loads(cached)],
                        cached=True,
                    )
            except Exception as exc:
                logger.warning("search_service.cache_read_failed", error=str(exc))

        candidate_limit = min(payload.limit * 3, 50)

        # 1. Semantic retrieval
        embedding = (await self.llm.embed([payload.query]))[0]
        semantic_contexts = await self.vector_store.semantic_search(
            payload.repository_id,
            embedding,
            limit=candidate_limit,
            embedding_model=embedding_model,
        )

        # 2. Lexical full-text retrieval
        lexical_contexts = await self.vector_store.lexical_search(
            payload.repository_id,
            payload.query,
            limit=candidate_limit,
        )

        # 3. Exact identifier retrieval
        symbol_query = exact_symbol or (payload.query.strip() if IDENTIFIER_RE.match(payload.query.strip()) else "")
        symbol_contexts: list[RetrievedContext] = []
        if symbol_query:
            symbol_contexts = await self.vector_store.symbol_search(
                payload.repository_id,
                symbol_query,
                limit=candidate_limit,
            )

        # 4. Reciprocal Rank Fusion
        ranked_sets: list[tuple[list[RetrievedContext], float]] = [
            (semantic_contexts, 1.0),
            (lexical_contexts, 0.8),
        ]
        if symbol_contexts:
            ranked_sets.append((symbol_contexts, 1.2))

        fused_contexts = reciprocal_rank_fusion(ranked_sets, k=60, limit=payload.limit)
        results = [self._context_to_result(ctx) for ctx in fused_contexts]

        if self.redis is not None:
            try:
                await self.redis.setex(cache_key, 60, json.dumps([item.model_dump() for item in results]))
            except Exception as exc:
                logger.warning("search_service.cache_write_failed", error=str(exc))

        return SearchResponse(results=results, cached=False)

    def _context_to_result(self, context: RetrievedContext) -> SearchResult:
        return SearchResult(
            path=context.path,
            start_line=context.start_line,
            end_line=context.end_line,
            content=context.content,
            score=context.score,
            symbol=context.symbol,
            symbol_type=context.symbol_type,
            parent_scope=context.parent_scope,
        )
