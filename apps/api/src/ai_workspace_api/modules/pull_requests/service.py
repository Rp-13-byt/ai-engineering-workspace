import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.models import PullRequestDraft
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.github import GitHubClient
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.infrastructure.vector_store import VectorStore
from ai_workspace_api.modules.pull_requests.schemas import PullRequestGenerateRequest


class PullRequestService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.llm = LLMGateway(settings)
        self.vector_store = VectorStore(session)

    async def generate(
        self,
        payload: PullRequestGenerateRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> PullRequestDraft:
        repository = await get_repository_for_organization(
            self.session,
            organization_id,
            payload.repository_id,
        )
        embedding = (await self.llm.embed([payload.instructions]))[0]
        contexts = await self.vector_store.semantic_search(repository.id, embedding, limit=10)
        draft_payload = await self.llm.generate_pull_request(payload.instructions, contexts)
        draft = PullRequestDraft(
            repository_id=repository.id,
            created_by_id=user_id,
            title=draft_payload["title"],
            body=draft_payload["body"],
            branch_name=draft_payload["branch_name"],
            diff=draft_payload["diff"],
            status="draft",
        )
        if payload.open_on_github:
            url = await GitHubClient().open_pull_request(
                repository.owner,
                repository.name,
                draft.title,
                draft.body,
                draft.branch_name,
                repository.default_branch,
            )
            draft.github_url = url
            draft.status = "opened"
        self.session.add(draft)
        await self.session.commit()
        return draft
