from typing import Literal, Annotated

from pydantic import Field, TypeAdapter

from .base_message import GameMessage, LobbyMessage
from .requests.game_command_payload import GameCommandPayload
from .requests.lobby_command_payload import LobbyCommandPayload


class GameCommandMessage(GameMessage):
    message_type: Literal["Command"] = "Command"
    payload: GameCommandPayload


class LobbyCommandMessage(LobbyMessage):
    message_type: Literal["Command"] = "Command"
    payload: LobbyCommandPayload


IncomingMessage = Annotated[
    GameCommandMessage | LobbyCommandMessage, Field(discriminator="topic")
]
"""Сообщения, которые клиент отправляет серверу"""

IncomingMessageAdapter = TypeAdapter(IncomingMessage)
