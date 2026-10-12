from uuid import UUID

from presentation.api.v1.dtos.responses.user_response import UserResponse
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSLobbyDataPayload(BaseWebSocketMessage):
    id: str
    participants: list[UserResponse]
    admin_id: UUID
    max_players: int
