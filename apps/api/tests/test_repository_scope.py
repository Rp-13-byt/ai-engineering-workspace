import uuid

import pytest

from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import Conversation, Repository
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.modules.chat.schemas import ChatRequest
from ai_workspace_api.modules.chat.service import ChatService


class FakeSession:
    def __init__(self, values: dict[tuple[type, uuid.UUID], object] | None = None) -> None:
        self.values = values or {}
        self.added: list[object] = []
        self.flushed = False

    async def get(self, model: type, item_id: uuid.UUID) -> object | None:
        return self.values.get((model, item_id))

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_get_repository_for_organization_rejects_cross_org_repository() -> None:
    repository_id = uuid.uuid4()
    requested_org_id = uuid.uuid4()
    repository = Repository(
        id=repository_id,
        organization_id=uuid.uuid4(),
        owner="owner",
        name="repo",
        remote_url="https://github.com/owner/repo.git",
    )
    session = FakeSession({(Repository, repository_id): repository})

    with pytest.raises(ApiError) as exc_info:
        await get_repository_for_organization(session, requested_org_id, repository_id)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_chat_conversation_scope_rejects_mismatched_repository() -> None:
    repository_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conversation = Conversation(
        id=conversation_id,
        repository_id=uuid.uuid4(),
        created_by_id=user_id,
        title="Existing conversation",
    )
    session = FakeSession({(Conversation, conversation_id): conversation})
    from ai_workspace_api.core.config import Settings
    service = ChatService(session=session, settings=Settings())
    payload = ChatRequest(
        repository_id=repository_id,
        conversation_id=conversation_id,
        message="Explain the auth flow",
    )

    with pytest.raises(ApiError) as exc_info:
        await service._get_or_create_conversation(payload, user_id)

    assert exc_info.value.status_code == 404
