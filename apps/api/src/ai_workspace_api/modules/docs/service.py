import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.infrastructure.vector_store import VectorStore
from ai_workspace_api.modules.docs.schemas import GenerationRequest


class DocumentationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.llm = LLMGateway(settings)
        self.vector_store = VectorStore(session)

    async def generate_docs(self, payload: GenerationRequest, organization_id: uuid.UUID) -> str:
        contexts = await self._contexts(payload, organization_id)
        return await self.llm.generate_documentation(payload.target, contexts)

    async def generate_tests(self, payload: GenerationRequest, organization_id: uuid.UUID) -> str:
        contexts = await self._contexts(payload, organization_id)
        return await self.llm.generate_tests(payload.target, contexts)

    async def detect_bugs(
        self,
        payload: GenerationRequest,
        organization_id: uuid.UUID,
    ) -> list[dict[str, str]]:
        contexts = await self._contexts(payload, organization_id)
        return await self.llm.detect_bugs(contexts)

    async def _contexts(self, payload: GenerationRequest, organization_id: uuid.UUID):
        await get_repository_for_organization(self.session, organization_id, payload.repository_id)
        embedding = (await self.llm.embed([payload.target]))[0]
        return await self.vector_store.semantic_search(payload.repository_id, embedding, limit=12)
