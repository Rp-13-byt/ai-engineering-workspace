import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_organization_id, require_permission
from ai_workspace_api.core.models import User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.docs.schemas import (
    BugDetectionResponse,
    BugFinding,
    DocumentationResponse,
    GenerationRequest,
    TestGenerationResponse,
)
from ai_workspace_api.modules.docs.service import DocumentationService

router = APIRouter(prefix="/docs", tags=["documentation"])


def get_documentation_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DocumentationService:
    return DocumentationService(session, settings)


@router.post("/generate", response_model=DocumentationResponse)
async def generate_docs(
    payload: GenerationRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.use_ai)),
    service: DocumentationService = Depends(get_documentation_service),
) -> DocumentationResponse:
    return DocumentationResponse(markdown=await service.generate_docs(payload, organization_id))


@router.post("/tests", response_model=TestGenerationResponse)
async def generate_tests(
    payload: GenerationRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.use_ai)),
    service: DocumentationService = Depends(get_documentation_service),
) -> TestGenerationResponse:
    return TestGenerationResponse(test_plan=await service.generate_tests(payload, organization_id))


@router.post("/bugs", response_model=BugDetectionResponse)
async def detect_bugs(
    payload: GenerationRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.use_ai)),
    service: DocumentationService = Depends(get_documentation_service),
) -> BugDetectionResponse:
    findings = await service.detect_bugs(payload, organization_id)
    return BugDetectionResponse(findings=[BugFinding(**finding) for finding in findings])
