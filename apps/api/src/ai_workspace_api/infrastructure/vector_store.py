import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.models import CodeChunk, CodeDocument
from ai_workspace_api.infrastructure.llm import RetrievedContext


def reciprocal_rank_fusion(
    ranked_result_sets: list[tuple[list[RetrievedContext], float]],
    k: int = 60,
    limit: int = 8,
) -> list[RetrievedContext]:
    """Combine rankings using Reciprocal Rank Fusion (RRF).

    score(d) = sum_m (weight_m / (k + rank_m(d)))
    """
    scores: dict[tuple[str, int, int], float] = {}
    context_map: dict[tuple[str, int, int], RetrievedContext] = {}

    for results, weight in ranked_result_sets:
        for rank, ctx in enumerate(results, start=1):
            key = (ctx.path, ctx.start_line, ctx.end_line)
            if key not in context_map:
                context_map[key] = ctx
            rrf_delta = weight / (k + rank)
            scores[key] = scores.get(key, 0.0) + rrf_delta

    # Sort items by fused RRF score descending
    sorted_keys = sorted(scores.keys(), key=lambda k_val: scores[k_val], reverse=True)

    fused_results: list[RetrievedContext] = []
    for key in sorted_keys[:limit]:
        original_ctx = context_map[key]
        fused_score = scores[key]
        fused_results.append(
            RetrievedContext(
                path=original_ctx.path,
                start_line=original_ctx.start_line,
                end_line=original_ctx.end_line,
                content=original_ctx.content,
                score=round(fused_score, 6),
                symbol=original_ctx.symbol,
                symbol_type=original_ctx.symbol_type,
                parent_scope=original_ctx.parent_scope,
            )
        )

    return fused_results


class VectorStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def semantic_search(
        self,
        repository_id: uuid.UUID,
        embedding: list[float],
        limit: int = 8,
        embedding_model: str | None = None,
    ) -> list[RetrievedContext]:
        distance = CodeChunk.embedding.cosine_distance(embedding).label("distance")
        conditions = [
            CodeDocument.repository_id == repository_id,
            CodeChunk.embedding.is_not(None),
        ]
        if embedding_model:
            conditions.append(
                or_(
                    CodeChunk.embedding_model == embedding_model,
                    CodeChunk.embedding_model.is_(None),
                )
            )

        statement = (
            select(CodeChunk, CodeDocument.path, distance)
            .join(CodeDocument, CodeDocument.id == CodeChunk.document_id)
            .where(*conditions)
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
                symbol=chunk.symbol,
                symbol_type=chunk.symbol_type,
                parent_scope=chunk.parent_scope,
            )
            for chunk, path, distance_value in rows
        ]

    async def lexical_search(
        self,
        repository_id: uuid.UUID,
        query: str,
        limit: int = 8,
    ) -> list[RetrievedContext]:
        """PostgreSQL Full-Text Search on chunk content with rank scoring."""
        # Clean query tokens for plainto_tsquery or ILIKE fallback
        query_text = query.strip()
        if not query_text:
            return []

        results: list[tuple[CodeChunk, str, float]] = []
        try:
            ts_query = func.plainto_tsquery("english", query_text)
            ts_vector = func.to_tsvector("english", CodeChunk.content)
            rank = func.ts_rank(ts_vector, ts_query).label("rank")

            statement = (
                select(CodeChunk, CodeDocument.path, rank)
                .join(CodeDocument, CodeDocument.id == CodeChunk.document_id)
                .where(
                    CodeDocument.repository_id == repository_id,
                    ts_vector.op("@@")(ts_query),
                )
                .order_by(rank.desc())
                .limit(limit)
            )
            rows = (await self.session.execute(statement)).all()
            results = [(chunk, path, float(rank_val)) for chunk, path, rank_val in rows]
        except Exception:
            # Fallback for dialect without tsvector support (e.g. SQLite in unit tests)
            statement = (
                select(CodeChunk, CodeDocument.path)
                .join(CodeDocument, CodeDocument.id == CodeChunk.document_id)
                .where(
                    CodeDocument.repository_id == repository_id,
                    CodeChunk.content.ilike(f"%{query_text}%"),
                )
                .limit(limit)
            )
            raw_rows = (await self.session.execute(statement)).all()
            results = [(chunk, path, 1.0) for chunk, path in raw_rows]

        return [
            RetrievedContext(
                path=path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                score=score_val,
                symbol=chunk.symbol,
                symbol_type=chunk.symbol_type,
                parent_scope=chunk.parent_scope,
            )
            for chunk, path, score_val in results
        ]

    async def symbol_search(
        self,
        repository_id: uuid.UUID,
        symbol_name: str,
        limit: int = 8,
    ) -> list[RetrievedContext]:
        """Exact and prefix identifier lookup on chunk symbol names."""
        clean_name = symbol_name.strip()
        if not clean_name:
            return []

        statement = (
            select(CodeChunk, CodeDocument.path)
            .join(CodeDocument, CodeDocument.id == CodeChunk.document_id)
            .where(
                CodeDocument.repository_id == repository_id,
                or_(
                    CodeChunk.symbol == clean_name,
                    CodeChunk.symbol.ilike(f"{clean_name}%"),
                ),
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
                score=1.0 if chunk.symbol == clean_name else 0.8,
                symbol=chunk.symbol,
                symbol_type=chunk.symbol_type,
                parent_scope=chunk.parent_scope,
            )
            for chunk, path in rows
        ]
