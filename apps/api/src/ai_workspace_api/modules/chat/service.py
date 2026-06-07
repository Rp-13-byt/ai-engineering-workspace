import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import ChatMessage, Conversation
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.infrastructure.vector_store import VectorStore
from ai_workspace_api.modules.chat.schemas import ChatRequest, ChatResponse, Citation


class ChatService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.llm = LLMGateway(settings)
        self.vector_store = VectorStore(session)

    async def answer(
        self,
        payload: ChatRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ChatResponse:
        await get_repository_for_organization(self.session, organization_id, payload.repository_id)
        embedding = (await self.llm.embed([payload.message]))[0]
        contexts = await self.vector_store.hybrid_search(
            repository_id=payload.repository_id,
            query=payload.message,
            embedding=embedding,
            limit=8,
        )
        conversation = await self._get_or_create_conversation(payload, user_id)
        
        history_stmt = select(ChatMessage).where(
            ChatMessage.conversation_id == conversation.id
        ).order_by(ChatMessage.created_at.asc())
        history = list((await self.session.scalars(history_stmt)).all())
        
        self.session.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="user",
                content=payload.message,
                citations=[],
            )
        )
        answer = await self.llm.answer_code_question(payload.message, contexts, history)
        citations = [
            Citation(
                path=context.path,
                start_line=context.start_line,
                end_line=context.end_line,
                score=context.score,
            )
            for context in contexts
        ]
        self.session.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                citations=[citation.model_dump() for citation in citations],
            )
        )
        await self.session.commit()
        return ChatResponse(
            conversation_id=conversation.id,
            answer=answer,
            citations=citations,
            created_at=datetime.now(UTC),
        )

    async def _get_or_create_conversation(
        self,
        payload: ChatRequest,
        user_id: uuid.UUID,
    ) -> Conversation:
        if payload.conversation_id:
            conversation = await self.session.get(Conversation, payload.conversation_id)
            if (
                conversation is not None
                and conversation.repository_id == payload.repository_id
                and conversation.created_by_id == user_id
            ):
                return conversation
            raise ApiError("Conversation not found", status.HTTP_404_NOT_FOUND)
        conversation = Conversation(
            repository_id=payload.repository_id,
            created_by_id=user_id,
            title=payload.message[:120],
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation
