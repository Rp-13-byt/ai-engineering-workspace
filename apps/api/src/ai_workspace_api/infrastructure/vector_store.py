import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.models import CodeChunk, CodeDocument
from ai_workspace_api.infrastructure.llm import RetrievedContext


class VectorStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def semantic_search(
        self,
        repository_id: uuid.UUID,
        embedding: list[float],
        limit: int = 8,
    ) -> list[RetrievedContext]:
        distance = CodeChunk.embedding.cosine_distance(embedding).label("distance")
        statement = (
            select(CodeChunk, CodeDocument.path, distance)
            .join(CodeDocument, CodeDocument.id == CodeChunk.document_id)
            .where(CodeDocument.repository_id == repository_id, CodeChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            RetrievedContext(
                path=path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                score=1.0 - float(distance_value),
            )
            for chunk, path, distance_value in rows
        ]
    async def keyword_search(
        self,
        repository_id: uuid.UUID,
        query: str,
        limit: int = 8,
    ) -> list[RetrievedContext]:
        from sqlalchemy import or_
        
        search_term = f"%{query}%"
        statement = (
            select(CodeChunk, CodeDocument.path)
            .join(CodeDocument, CodeDocument.id == CodeChunk.document_id)
            .where(
                CodeDocument.repository_id == repository_id,
                or_(
                    CodeChunk.content.ilike(search_term),
                    CodeChunk.symbol.ilike(search_term),
                    CodeDocument.path.ilike(search_term),
                )
            )
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            RetrievedContext(
                path=path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                score=1.0,
            )
            for chunk, path in rows
        ]

    async def hybrid_search(
        self,
        repository_id: uuid.UUID,
        query: str,
        embedding: list[float],
        limit: int = 8,
    ) -> list[RetrievedContext]:
        fetch_limit = limit * 2
        vector_results = await self.semantic_search(repository_id, embedding, fetch_limit)
        keyword_results = await self.keyword_search(repository_id, query, fetch_limit)
        
        k = 60
        rrf_scores: dict[str, float] = {}
        context_map: dict[str, RetrievedContext] = {}
        
        def _doc_key(ctx: RetrievedContext) -> str:
            return f"{ctx.path}:{ctx.start_line}-{ctx.end_line}"
            
        for rank, ctx in enumerate(vector_results):
            key = _doc_key(ctx)
            context_map[key] = ctx
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            
        for rank, ctx in enumerate(keyword_results):
            key = _doc_key(ctx)
            if key not in context_map:
                context_map[key] = ctx
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        
        final_results = []
        for key in sorted_keys[:limit]:
            ctx = context_map[key]
            ctx.score = rrf_scores[key]
            final_results.append(ctx)
            
        return final_results
