from typing import Literal, Annotated

from pydantic import Field, TypeAdapter

from .base_message import BaseMessage
from .responses.ws_game_data_payload import WSGameDataPayload
from .responses.ws_game_info_payload import WSGameInfoPayload
from .responses.ws_game_role_payload import WSGameRolePayload
from .responses.ws_lobby_data_payload import WSLobbyDataPayload
from .requests.ws_game_command_payload import WSGameCommandPayload
from .requests.ws_lobby_command_payload import WSLobbyCommandPayload
from .responses.ws_game_new_stage_payload import WSGameNewStagePayload
from .responses.ws_game_action_request_payload import (
    WSGameActionRequestPayload,
)
from .responses.ws_user_connection_message_payload import (
    WSUserConnectionMessagePayload,
)


GamePayload = (
    WSGameCommandPayload
    | WSGameInfoPayload
    | WSGameActionRequestPayload
    | WSGameNewStagePayload
    | WSGameDataPayload
    | WSGameRolePayload
    | WSUserConnectionMessagePayload
)
"""Payload сообщений с топиком Game"""

LobbyPayload = (
    WSLobbyCommandPayload
    | WSLobbyDataPayload
    | WSUserConnectionMessagePayload
    | WSGameInfoPayload
)
"""Payload сообщений с топиком Lobby (Info используется для ошибок)"""

SystemPayload = WSGameInfoPayload
"""Payload системных сообщений"""


class GameMessage(BaseMessage):
    topic: Literal["Game"] = "Game"
    payload: GamePayload


class LobbyMessage(BaseMessage):
    topic: Literal["Lobby"] = "Lobby"
    payload: LobbyPayload


class SystemMessage(BaseMessage):
    topic: Literal["System"] = "System"
    payload: SystemPayload


OutgoingMessage = GameMessage | LobbyMessage | SystemMessage
"""Сообщения, которые сервер отправляет клиенту"""

IncomingMessage = Annotated[OutgoingMessage, Field(discriminator="topic")]
"""Сообщения, которые клиент отправляет серверу"""

IncomingMessageAdapter = TypeAdapter(IncomingMessage)
