from typing import Literal, Annotated

from pydantic import Field, TypeAdapter

from .base_message import GameMessage, LobbyMessage
from .message_type import MessageType
from .payloads.game_command_payload import GameCommandPayload
from .payloads.lobby_command_payload import LobbyCommandPayload


class GameCommandMessage(GameMessage):
    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND
    payload: GameCommandPayload


class LobbyCommandMessage(LobbyMessage):
    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND
    payload: LobbyCommandPayload


IncomingMessage = Annotated[
    GameCommandMessage | LobbyCommandMessage, Field(discriminator="topic")
]
"""Сообщения, которые клиент отправляет серверу"""

IncomingMessageAdapter = TypeAdapter(IncomingMessage)
