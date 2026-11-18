from uuid import UUID

from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)
from presentation.api.v1.dtos.responses.user_response import UserResponse


class LobbyDataPayload(BasePayload):
    id: str
    participants: list[UserResponse]
    admin_id: UUID
    max_players: int
