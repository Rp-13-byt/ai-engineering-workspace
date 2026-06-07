import json
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.infrastructure.vector_store import VectorStore
from ai_workspace_api.modules.search.schemas import SearchRequest, SearchResponse, SearchResult


class SearchService:
    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings) -> None:
        self.session = session
        self.redis = redis
        self.llm = LLMGateway(settings)
        self.vector_store = VectorStore(session)

    async def semantic_search(
        self,
        payload: SearchRequest,
        organization_id: uuid.UUID,
    ) -> SearchResponse:
        await get_repository_for_organization(self.session, organization_id, payload.repository_id)
        cache_key = f"hybrid-search:{payload.repository_id}:{payload.limit}:{payload.query}"
        cached = await self.redis.get(cache_key)
        if cached:
            return SearchResponse(
                results=[SearchResult(**item) for item in json.loads(cached)],
                cached=True,
            )

        embedding = (await self.llm.embed([payload.query]))[0]
        contexts = await self.vector_store.hybrid_search(
            repository_id=payload.repository_id,
            query=payload.query,
            embedding=embedding,
            limit=payload.limit,
        )
        results = [
            SearchResult(
                path=context.path,
                start_line=context.start_line,
                end_line=context.end_line,
                content=context.content,
                score=context.score,
            )
            for context in contexts
        ]
        await self.redis.setex(cache_key, 60, json.dumps([item.model_dump() for item in results]))
        return SearchResponse(results=results)
