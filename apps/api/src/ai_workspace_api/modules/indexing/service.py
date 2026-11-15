import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.logging import get_logger
from ai_workspace_api.core.models import CodeChunk, CodeDocument, Repository, RepositoryStatus
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.github import GitHubClient
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.modules.indexing.parsers import (
    ParsedChunk,
    get_parser_for_language,
)
from ai_workspace_api.modules.indexing.schemas import IndexingStats

logger = get_logger(__name__)

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rs": "rust",
    ".rb": "ruby",
    ".cs": "csharp",
    ".sql": "sql",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


@dataclass(frozen=True)
class Chunk:
    start_line: int
    end_line: int
    content: str


class IndexingService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.llm = LLMGateway(settings)

    async def get_status(self, repository_id: uuid.UUID, organization_id: uuid.UUID) -> Repository:
        return await get_repository_for_organization(self.session, organization_id, repository_id)

    async def index_repository(
        self,
        repository_id: uuid.UUID,
        target_commit: str | None = None,
    ) -> IndexingStats:
        repository = await self.session.get(Repository, repository_id)
        if repository is None:
            raise ApiError("Repository not found", status.HTTP_404_NOT_FOUND)

        target_ref = target_commit or repository.default_branch
        current_model = self.settings.embedding_model

        # Check if embedding model was updated, necessitating full re-embedding
        model_changed = (
            repository.embedding_model is not None
            and repository.embedding_model != current_model
        )

        repository.indexing_status = RepositoryStatus.indexing
        await self.session.commit()

        documents_indexed = 0
        chunks_indexed = 0
        skipped_files = 0
        unchanged_files = 0
        modified_files = 0
        added_files = 0
        deleted_files = 0

        try:
            github = GitHubClient()
            tree = await github.get_tree(
                repository.owner,
                repository.name,
                target_ref,
            )

            # Query existing indexed documents
            existing_docs_stmt = select(CodeDocument).where(CodeDocument.repository_id == repository.id)
            existing_docs_list = (await self.session.scalars(existing_docs_stmt)).all()
            existing_docs: dict[str, CodeDocument] = {doc.path: doc for doc in existing_docs_list}

            # Map valid tree files
            tree_files: dict[str, dict[str, Any]] = {}
            for item in tree:
                path = item.get("path", "")
                is_too_large = item.get("size", 0) > 300_000
                if item.get("type") != "blob" or not self._is_indexable(path) or is_too_large:
                    skipped_files += 1
                    continue
                tree_files[path] = item

            # 1. Remove deleted files (in existing_docs but not in current tree)
            deleted_paths = set(existing_docs.keys()) - set(tree_files.keys())
            for path in deleted_paths:
                doc_to_delete = existing_docs[path]
                await self.session.delete(doc_to_delete)
                deleted_files += 1

            # 2. Process added, modified, or unchanged files
            for path, item in tree_files.items():
                existing_doc = existing_docs.get(path)

                content = await github.get_file_content(
                    repository.owner,
                    repository.name,
                    path,
                    target_ref,
                )
                content_hash = self._sha256(content)

                # Skip unchanged files if content hash matches and embedding model has not changed
                if existing_doc is not None and not model_changed and existing_doc.content_hash == content_hash:
                    unchanged_files += 1
                    if existing_doc.commit_sha != target_ref:
                        existing_doc.commit_sha = target_ref
                    continue

                lang = self._language(path)
                parser = get_parser_for_language(lang)
                parsed_chunks: list[ParsedChunk] = parser.parse_and_chunk(content, file_path=path)

                # Embed parsed chunks
                chunk_texts = [c.content for c in parsed_chunks]
                embeddings = await self.llm.embed(chunk_texts) if chunk_texts else []

                if existing_doc is not None:
                    # Modified file: replace existing chunks
                    modified_files += 1
                    existing_doc.commit_sha = target_ref
                    existing_doc.content_hash = content_hash
                    existing_doc.size_bytes = len(content.encode("utf-8"))
                    existing_doc.language = lang
                    await self.session.execute(
                        delete(CodeChunk).where(CodeChunk.document_id == existing_doc.id)
                    )
                    doc_id = existing_doc.id
                else:
                    # Added file: create new document
                    added_files += 1
                    new_doc = CodeDocument(
                        repository_id=repository.id,
                        path=path,
                        language=lang,
                        commit_sha=target_ref,
                        content_hash=content_hash,
                        size_bytes=len(content.encode("utf-8")),
                    )
                    self.session.add(new_doc)
                    await self.session.flush()
                    doc_id = new_doc.id

                for p_chunk, emb in zip(parsed_chunks, embeddings, strict=True):
                    self.session.add(
                        CodeChunk(
                            document_id=doc_id,
                            start_line=p_chunk.start_line,
                            end_line=p_chunk.end_line,
                            symbol=p_chunk.symbol,
                            symbol_type=p_chunk.symbol_type,
                            parent_scope=p_chunk.parent_scope,
                            content=p_chunk.content,
                            content_hash=self._sha256(p_chunk.content),
                            embedding=emb,
                            embedding_model=current_model,
                        )
                    )

                documents_indexed += 1
                chunks_indexed += len(parsed_chunks)

            # Successfully indexed: update repository status and metadata
            repository.indexing_status = RepositoryStatus.indexed
            repository.last_indexed_commit = target_ref
            repository.embedding_model = current_model
            await self.session.commit()

            return IndexingStats(
                documents_indexed=documents_indexed,
                chunks_indexed=chunks_indexed,
                skipped_files=skipped_files,
                unchanged_files=unchanged_files,
                modified_files=modified_files,
                added_files=added_files,
                deleted_files=deleted_files,
            )

        except Exception as exc:
            # Preserve existing valid index on failure through rollback
            await self.session.rollback()
            logger.exception("indexing.failed", repository_id=str(repository_id), error=str(exc))
            try:
                # Update status to failed without losing previously committed chunks
                failed_repo = await self.session.get(Repository, repository_id)
                if failed_repo is not None:
                    failed_repo.indexing_status = RepositoryStatus.failed
                    await self.session.commit()
            except Exception:
                pass
            raise

    def _is_indexable(self, path: str) -> bool:
        return any(path.endswith(extension) for extension in LANGUAGE_BY_EXTENSION)

    def _language(self, path: str) -> str | None:
        for extension, language in LANGUAGE_BY_EXTENSION.items():
            if path.endswith(extension):
                return language
        return None

    def _chunk_content(self, content: str, max_lines: int = 120) -> list[Chunk]:
        """Legacy helper preserved for backwards compatibility with tests and callers."""
        lines = content.splitlines()
        if not lines:
            return []
        chunks: list[Chunk] = []
        for start in range(0, len(lines), max_lines):
            end = min(start + max_lines, len(lines))
            chunks.append(
                Chunk(
                    start_line=start + 1,
                    end_line=end,
                    content="\n".join(lines[start:end]),
                )
            )
        return chunks

    def _sha256(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
