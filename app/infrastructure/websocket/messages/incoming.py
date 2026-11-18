from typing import Literal, Annotated

from pydantic import Field, TypeAdapter

from .base_message import GameMessage, LobbyMessage
from .requests.ws_game_command_payload import WSGameCommandPayload
from .requests.ws_lobby_command_payload import WSLobbyCommandPayload


class GameCommandMessage(GameMessage):
    message_type: Literal["Command"] = "Command"
    payload: WSGameCommandPayload


class LobbyCommandMessage(LobbyMessage):
    message_type: Literal["Command"] = "Command"
    payload: WSLobbyCommandPayload


IncomingMessage = Annotated[
    GameCommandMessage | LobbyCommandMessage, Field(discriminator="topic")
]
"""Сообщения, которые клиент отправляет серверу"""

IncomingMessageAdapter = TypeAdapter(IncomingMessage)
