from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSGameInfoPayload(BaseWebSocketMessage):
    text: str
