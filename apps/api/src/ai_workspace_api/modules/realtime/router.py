import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.models import Membership, User
from ai_workspace_api.core.security import InvalidTokenError, decode_access_token
from ai_workspace_api.modules.realtime.manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/{organization_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    organization_id: uuid.UUID,
    token: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        payload = decode_access_token(token, settings)
        user_id = uuid.UUID(str(payload["sub"]))
    except (InvalidTokenError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    membership = await session.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
    )
    if membership is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(organization_id, user_id, websocket)
    try:
        while True:
            event = await websocket.receive_json()
            if event.get("type") == "heartbeat":
                await websocket.send_json({"type": "heartbeat.ack"})
            elif event.get("type") == "task.updated":
                await manager.broadcast(organization_id, event)
    except WebSocketDisconnect:
        await manager.disconnect(organization_id, websocket)
