from domain.enums import RoleEnum
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class GameRolePayload(BasePayload):
    text: str
    role: RoleEnum
