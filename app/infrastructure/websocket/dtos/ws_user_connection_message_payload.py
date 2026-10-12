from presentation.api.v1.dtos.responses import UserResponse, LobbyResponse
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSUserConnectionMessagePayload(BaseWebSocketMessage):
    text: str
    user: UserResponse
    lobby: LobbyResponse | None
