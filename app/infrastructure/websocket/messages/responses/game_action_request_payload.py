from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class GameActionRequestPayload(BasePayload):
    text: str
    timeout: int
