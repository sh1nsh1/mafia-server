from uuid import UUID

from domain.enums import WebSocketGameCommandActionTypeEnum
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class WSGameCommandPayload(BasePayload):
    action_type: WebSocketGameCommandActionTypeEnum
    actor_id: UUID
    target_id: UUID | None
    room_id: str
