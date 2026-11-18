from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class GameInfoPayload(BasePayload):
    text: str
