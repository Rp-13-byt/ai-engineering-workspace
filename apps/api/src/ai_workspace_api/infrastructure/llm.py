import hashlib
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_workspace_api.core.config import Settings
from ai_workspace_api.infrastructure.embeddings.base import EmbeddingProvider
from ai_workspace_api.infrastructure.embeddings.cache import EmbeddingCache
from ai_workspace_api.infrastructure.embeddings.factory import get_embedding_provider

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True)
class RetrievedContext:
    path: str
    start_line: int
    end_line: int
    content: str
    score: float
    symbol: str | None = None
    symbol_type: str | None = None
    parent_scope: str | None = None


class LLMGateway:
    def __init__(
        self,
        settings: Settings | None = None,
        redis: "Redis | None" = None,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.redis = redis
        self.embedding_provider = provider or get_embedding_provider(self.settings)
        self.embedding_cache = EmbeddingCache(redis)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # 1. Check cache with stable composite key
        hits, misses = await self.embedding_cache.get_many(
            self.embedding_provider.name,
            self.embedding_provider.model_name,
            texts,
        )

        results: list[list[float] | None] = [None] * len(texts)
        for idx, vec in hits.items():
            results[idx] = vec

        # 2. Batch misses to avoid payload limits
        if misses:
            batch_size = max(1, self.settings.embedding_batch_size)
            new_cached_items: list[tuple[int, str, list[float]]] = []

            for offset in range(0, len(misses), batch_size):
                batch = misses[offset : offset + batch_size]
                batch_texts = [text for _, text in batch]
                batch_vectors = await self.embedding_provider.embed_batch(batch_texts)

                for (orig_idx, text), vec in zip(batch, batch_vectors, strict=True):
                    results[orig_idx] = vec
                    new_cached_items.append((orig_idx, text, vec))

            # 3. Store new vectors in cache
            await self.embedding_cache.put_many(
                self.embedding_provider.name,
                self.embedding_provider.model_name,
                new_cached_items,
            )

        return [vec for vec in results if vec is not None]

    async def answer_code_question(self, question: str, contexts: list[RetrievedContext]) -> str:
        if not contexts:
            return (
                "I could not find indexed context for that repository yet. "
                "Import and index the repository, then ask again."
            )
        citations = ", ".join(f"{ctx.path}:{ctx.start_line}-{ctx.end_line}" for ctx in contexts[:4])
        return (
            f"Based on the indexed code, the highest-signal references are {citations}.\n\n"
            f"Question: {question}\n\n"
            "Recommended next step: inspect those symbols, write a small regression test, "
            "then generate a scoped patch through the PR workflow."
        )

    async def generate_pull_request(self, instructions: str, contexts: list[RetrievedContext]) -> dict[str, str]:
        summary = contexts[0].path if contexts else "repository"
        return {
            "title": f"AI change: {instructions[:72]}",
            "body": (
                "## Summary\n"
                f"- Implements requested change using retrieved context from `{summary}`.\n\n"
                "## Validation\n- Add or run focused tests before merge.\n"
            ),
            "branch_name": "ai/workspace-generated-change",
            "diff": self._sample_diff(instructions, contexts),
        }

    async def generate_tests(self, target: str, contexts: list[RetrievedContext]) -> str:
        context_paths = ", ".join(ctx.path for ctx in contexts[:3]) or target
        return (
            f"Create focused unit and integration tests for {target}.\n"
            f"Use fixtures around {context_paths} and verify error paths, concurrency, and caching."
        )

    async def detect_bugs(self, contexts: list[RetrievedContext]) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        for ctx in contexts:
            if "TODO" in ctx.content or "FIXME" in ctx.content:
                findings.append(
                    {
                        "path": ctx.path,
                        "severity": "medium",
                        "message": "Indexed code contains unresolved TODO/FIXME markers.",
                    }
                )
        return findings

    async def generate_documentation(self, target: str, contexts: list[RetrievedContext]) -> str:
        paths = "\n".join(f"- `{ctx.path}` lines {ctx.start_line}-{ctx.end_line}" for ctx in contexts[:8])
        return f"# Documentation for {target}\n\n## Relevant Code\n{paths or '- No indexed context found.'}\n"

    def _deterministic_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.settings.embedding_dimensions)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def _sample_diff(self, instructions: str, contexts: list[RetrievedContext]) -> str:
        path = contexts[0].path if contexts else "README.md"
        return (
            f"diff --git a/{path} b/{path}\n"
            "--- a/{path}\n"
            "+++ b/{path}\n"
            "@@\n"
            f"+# AI-generated implementation note: {instructions}\n"
        )
