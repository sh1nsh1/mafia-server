from domain.enums import GameStageEnum
from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class GameNewStagePayload(BasePayload):
    new_stage: GameStageEnum
    text: str
