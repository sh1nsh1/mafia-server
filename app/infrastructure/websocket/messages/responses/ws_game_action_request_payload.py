from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class WSGameActionRequestPayload(BasePayload):
    text: str
    timeout: int
