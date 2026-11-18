from presentation.api.v1.dtos.responses import UserResponse, LobbyResponse
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class UserConnectionPayload(BasePayload):
    message: str
    user: UserResponse
    lobby: LobbyResponse | None
