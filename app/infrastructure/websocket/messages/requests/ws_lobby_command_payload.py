from uuid import UUID

from domain.enums import RoleEnum, WebSocketLobbyCommandTypeEnum
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class WSLobbyCommandPayload(BasePayload):
    action_type: WebSocketLobbyCommandTypeEnum
    target_id: UUID | None
    room_id: str
    role_set: list[RoleEnum] | None
