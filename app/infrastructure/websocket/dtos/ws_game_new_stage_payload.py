from domain.enums import GameStageEnum
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSGameNewStagePayload(BaseWebSocketMessage):
    new_stage: GameStageEnum
    text: str
