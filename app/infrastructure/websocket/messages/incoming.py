from typing import Literal, Annotated

from pydantic import Field, TypeAdapter

from domain.enums import Topic

from .base_message import BaseMessage
from .message_type import MessageType
from .payloads.game_command_payload import GameCommandPayload
from .payloads.lobby_command_payload import LobbyCommandPayload


class GameCommandMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND
    payload: GameCommandPayload


class LobbyCommandMessage(BaseMessage):
    topic: Literal[Topic.LOBBY] = Topic.LOBBY
    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND
    payload: LobbyCommandPayload


IncomingMessage = Annotated[
    GameCommandMessage | LobbyCommandMessage, Field(discriminator="topic")
]
"""Сообщения, которые клиент отправляет серверу"""

IncomingMessageAdapter = TypeAdapter(IncomingMessage)
