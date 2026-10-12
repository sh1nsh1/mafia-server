from domain.enums import RoleEnum
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSGameRolePayload(BaseWebSocketMessage):
    text: str
    role: RoleEnum
