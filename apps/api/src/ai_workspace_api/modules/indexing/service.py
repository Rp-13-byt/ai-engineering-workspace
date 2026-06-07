import hashlib
import uuid

from fastapi import status
from prometheus_client import Counter, Histogram
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import (
    CodeChunk,
    CodeDocument,
    Repository,
    RepositoryBranch,
    RepositorySnapshot,
    RepositoryStatus,
)
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.github import GitHubClient
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.modules.indexing.chunking import SemanticChunker, detect_language
from ai_workspace_api.modules.indexing.file_filter import FileFilter
from ai_workspace_api.modules.indexing.schemas import IndexingStats

INDEXING_DOCUMENTS_TOTAL = Counter(
    "workspace_indexing_documents_total",
    "Total number of documents indexed",
)
INDEXING_CHUNKS_TOTAL = Counter(
    "workspace_indexing_chunks_total",
    "Total number of chunks indexed",
)
INDEXING_DURATION_SECONDS = Histogram(
    "workspace_indexing_duration_seconds",
    "Time taken to index a repository",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
)
INDEXING_ERRORS_TOTAL = Counter(
    "workspace_indexing_errors_total",
    "Total number of indexing errors",
    ["error_type"],
)

class IndexingService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.llm = LLMGateway(settings)
        self.chunker = SemanticChunker()

    async def get_status(self, repository_id: uuid.UUID, organization_id: uuid.UUID) -> Repository:
        return await get_repository_for_organization(self.session, organization_id, repository_id)

    @INDEXING_DURATION_SECONDS.time()
    async def index_repository(self, repository_id: uuid.UUID) -> IndexingStats:
        repository = await self.session.get(Repository, repository_id)
        if repository is None:
            raise ApiError("Repository not found", status.HTTP_404_NOT_FOUND)

        repository.indexing_status = RepositoryStatus.indexing
        await self.session.commit()

        snapshot = RepositorySnapshot(
            repository_id=repository.id,
            branch=repository.default_branch,
            commit_sha="pending",
        )
        self.session.add(snapshot)
        await self.session.commit()

        documents_indexed = 0
        chunks_indexed = 0
        skipped_files = 0
        deleted_files = 0
        is_incremental = False
        try:
            async with GitHubClient() as github:
                head_sha = await github.get_commit_sha(
                    repository.owner, repository.name, repository.default_branch
                )
                
                if repository.last_indexed_commit == head_sha:
                    repository.indexing_status = RepositoryStatus.indexed
                    snapshot.status = "skipped"
                    snapshot.commit_sha = head_sha
                    from sqlalchemy import func
                    snapshot.completed_at = func.now()
                    await self.session.commit()
                    return IndexingStats(
                        documents_indexed=0,
                        chunks_indexed=0,
                        skipped_files=0,
                        deleted_files=0,
                        is_incremental=True,
                    )
                    
                gitignore_content = await self._fetch_gitignore(
                    github, repository.owner, repository.name, repository.default_branch
                )
                file_filter = FileFilter(gitignore_content=gitignore_content)
                
                changed_files = None
                if repository.last_indexed_commit:
                    try:
                        changed_files = await github.compare_commits(
                            repository.owner, repository.name, repository.last_indexed_commit, head_sha
                        )
                        is_incremental = True
                    except Exception:
                        pass
                
                if is_incremental and changed_files is not None:
                    for cf in changed_files:
                        path = cf.filename
                        if cf.status in ("removed", "modified", "renamed", "changed"):
                            result = await self.session.execute(
                                delete(CodeDocument).where(
                                    CodeDocument.repository_id == repository.id,
                                    CodeDocument.path == path
                                )
                            )
                            deleted_files += result.rowcount
                            
                        if cf.status in ("added", "modified", "renamed", "copied", "changed"):
                            if not file_filter.should_index(path):
                                skipped_files += 1
                                continue
                            try:
                                content = await github.get_file_content(
                                    repository.owner, repository.name, path, head_sha
                                )
                            except Exception:
                                skipped_files += 1
                                continue
                            
                            doc, chunks = await self._index_file_content(
                                repository.id, path, head_sha, content
                            )
                            documents_indexed += 1
                            chunks_indexed += len(chunks)
                else:
                    await self.session.execute(
                        delete(CodeDocument).where(CodeDocument.repository_id == repository.id)
                    )
                    tree = await github.get_tree(
                        repository.owner, repository.name, head_sha
                    )
                    for item in tree:
                        path = item.get("path", "")
                        file_size = item.get("size", 0)
                        if item.get("type") != "blob" or not file_filter.should_index(path, file_size):
                            skipped_files += 1
                            continue
                        
                        try:
                            content = await github.get_file_content(
                                repository.owner, repository.name, path, head_sha
                            )
                        except Exception:
                            skipped_files += 1
                            continue
                            
                        doc, chunks = await self._index_file_content(
                            repository.id, path, head_sha, content
                        )
                        documents_indexed += 1
                        chunks_indexed += len(chunks)

            repository.indexing_status = RepositoryStatus.indexed
            repository.last_indexed_commit = head_sha
            
            progress_data = {
                "documents_indexed": documents_indexed,
                "chunks_indexed": chunks_indexed,
                "skipped_files": skipped_files,
                "deleted_files": deleted_files,
                "is_incremental": is_incremental,
            }
            new_meta = dict(repository.metadata_json) if isinstance(repository.metadata_json, dict) else {}
            new_meta["last_indexing_stats"] = progress_data
            repository.metadata_json = new_meta
            
            from sqlalchemy import func
            snapshot.commit_sha = head_sha
            snapshot.documents_count = documents_indexed
            snapshot.chunks_count = chunks_indexed
            snapshot.status = "completed"
            snapshot.completed_at = func.now()
            snapshot.metadata_json = progress_data
            
            branch_stmt = select(RepositoryBranch).where(
                RepositoryBranch.repository_id == repository.id,
                RepositoryBranch.name == repository.default_branch
            )
            branch = (await self.session.execute(branch_stmt)).scalar_one_or_none()
            if not branch:
                branch = RepositoryBranch(
                    repository_id=repository.id,
                    name=repository.default_branch,
                    last_commit_sha=head_sha,
                    is_default=True,
                )
                self.session.add(branch)
            else:
                branch.last_commit_sha = head_sha
            branch.last_indexed_at = func.now()
            
            await self.session.commit()
            
            INDEXING_DOCUMENTS_TOTAL.inc(documents_indexed)
            INDEXING_CHUNKS_TOTAL.inc(chunks_indexed)
            
            return IndexingStats(
                documents_indexed=documents_indexed,
                chunks_indexed=chunks_indexed,
                skipped_files=skipped_files,
                deleted_files=deleted_files,
                is_incremental=is_incremental,
            )
        except Exception as e:
            INDEXING_ERRORS_TOTAL.labels(error_type=type(e).__name__).inc()
            repository.indexing_status = RepositoryStatus.failed
            new_meta = dict(repository.metadata_json) if isinstance(repository.metadata_json, dict) else {}
            new_meta["last_indexing_error"] = str(e)
            repository.metadata_json = new_meta
            
            from sqlalchemy import func
            snapshot.status = "failed"
            snapshot.completed_at = func.now()
            snapshot.metadata_json = {"error": str(e)}
            
            await self.session.commit()
            raise

    async def _index_file_content(
        self, repository_id: uuid.UUID, path: str, commit_sha: str, content: str
    ) -> tuple[CodeDocument, list[CodeChunk]]:
        content_hash = self._sha256(content)
        language = detect_language(path)
        document = CodeDocument(
            repository_id=repository_id,
            path=path,
            language=language,
            commit_sha=commit_sha,
            content_hash=content_hash,
            size_bytes=len(content.encode("utf-8")),
        )
        self.session.add(document)
        await self.session.flush()
        
        chunks = self.chunker.chunk(content, language)
        embeddings = await self.llm.embed([chunk.content for chunk in chunks])
        code_chunks = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            code_chunk = CodeChunk(
                document_id=document.id,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                content_hash=self._sha256(chunk.content),
                embedding=embedding,
                symbol=chunk.symbol,
            )
            self.session.add(code_chunk)
            code_chunks.append(code_chunk)
            
        return document, code_chunks


    def _sha256(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    async def _fetch_gitignore(
        self,
        github: GitHubClient,
        owner: str,
        name: str,
        ref: str,
    ) -> str | None:
        try:
            return await github.get_file_content(owner, name, ".gitignore", ref)
        except Exception:
            return None
