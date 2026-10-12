from uuid import UUID

from domain.enums import RoleEnum, WebSocketLobbyCommandTypeEnum
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSLobbyCommandPayload(BaseWebSocketMessage):
    action_type: WebSocketLobbyCommandTypeEnum
    target_id: UUID | None
    room_id: str
    role_set: list[RoleEnum] | None
