from infrastructure.websocket.messages.base_payload import (
    BasePayload,
)


class WSGameInfoPayload(BasePayload):
    text: str
