from domain.enums import RoleEnum
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class WSGameRolePayload(BasePayload):
    text: str
    role: RoleEnum
