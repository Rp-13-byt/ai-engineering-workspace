import json
import uuid
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._users: dict[WebSocket, uuid.UUID] = {}

    async def connect(self, organization_id: uuid.UUID, user_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[organization_id].add(websocket)
        self._users[websocket] = user_id
        await self.broadcast(
            organization_id,
            {
                "type": "presence.joined",
                "user_id": str(user_id),
                "online": self.online_count(organization_id),
            },
        )

    async def disconnect(self, organization_id: uuid.UUID, websocket: WebSocket) -> None:
        user_id = self._users.pop(websocket, None)
        self._rooms[organization_id].discard(websocket)
        await self.broadcast(
            organization_id,
            {
                "type": "presence.left",
                "user_id": str(user_id) if user_id else None,
                "online": self.online_count(organization_id),
            },
        )

    async def broadcast(self, organization_id: uuid.UUID, event: dict) -> None:
        stale: list[WebSocket] = []
        payload = json.dumps(event)
        for websocket in self._rooms[organization_id]:
            try:
                await websocket.send_text(payload)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self._rooms[organization_id].discard(websocket)
            self._users.pop(websocket, None)

    def online_count(self, organization_id: uuid.UUID) -> int:
        return len(self._rooms[organization_id])


manager = ConnectionManager()
