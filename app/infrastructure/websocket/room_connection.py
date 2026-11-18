import asyncio
from uuid import UUID
from collections.abc import Callable, Awaitable

from fastapi import WebSocket

from infrastructure.websocket.messages import BaseMessage


class RoomConnection:
    send_state_message: Callable[[str, UUID], Awaitable[None]]
    last_action_request_message: BaseMessage | None

    def __init__(
        self,
        websocket: WebSocket,
        message_queue: asyncio.Queue[BaseMessage],
    ):
        self.websocket = websocket
        self.message_queue = message_queue
        self.is_disconnected = False
        self.is_callback_set = False
        self.last_action_request_message = None
