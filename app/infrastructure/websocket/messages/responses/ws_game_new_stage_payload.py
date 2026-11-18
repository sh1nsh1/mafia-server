from domain.enums import GameStageEnum
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class WSGameNewStagePayload(BasePayload):
    new_stage: GameStageEnum
    text: str
