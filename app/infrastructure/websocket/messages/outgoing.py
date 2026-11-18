from typing import Literal

from domain.enums import WebSocketTopic

from .base_message import BaseMessage, GameMessage, LobbyMessage
from .responses.ws_game_data_payload import WSGameDataPayload
from .responses.ws_game_info_payload import WSGameInfoPayload
from .responses.ws_game_role_payload import WSGameRolePayload
from .responses.ws_lobby_data_payload import WSLobbyDataPayload
from .responses.ws_game_new_stage_payload import WSGameNewStagePayload
from .responses.ws_game_action_request_payload import (
    WSGameActionRequestPayload,
)
from .responses.ws_user_connection_message_payload import (
    WSUserConnectionMessagePayload,
)


class GameInfoMessage(GameMessage):
    message_type: Literal["Info"] = "Info"
    payload: WSGameInfoPayload


class GameEventMessage(GameMessage):
    message_type: Literal["Event"] = "Event"
    payload: WSGameInfoPayload


class GameStartMessage(GameMessage):
    message_type: Literal["GameStart"] = "GameStart"
    payload: WSGameInfoPayload


class GameFinishMessage(GameMessage):
    message_type: Literal["GameFinish"] = "GameFinish"
    payload: WSGameInfoPayload


class GameActionRequestMessage(GameMessage):
    message_type: Literal["ActionRequest"] = "ActionRequest"
    payload: WSGameActionRequestPayload


class GameRoleMessage(GameMessage):
    message_type: Literal["Role"] = "Role"
    payload: WSGameRolePayload


class GameNewStageMessage(GameMessage):
    message_type: Literal["NewStage"] = "NewStage"
    payload: WSGameNewStagePayload


class GameDataMessage(GameMessage):
    message_type: Literal["GameData"] = "GameData"
    payload: WSGameDataPayload


class LobbyDataMessage(LobbyMessage):
    message_type: Literal["LobbyData"] = "LobbyData"
    payload: WSLobbyDataPayload


class ErrorMessage(BaseMessage):
    """Ошибка может прийти в любом топике (Game, Lobby, System)"""

    topic: WebSocketTopic
    message_type: Literal["Error"] = "Error"
    payload: WSGameInfoPayload


class UserConnectMessage(BaseMessage):
    """Подключение к комнате: топик зависит от того, лобби это или игра"""

    topic: WebSocketTopic
    message_type: Literal["UserConnect"] = "UserConnect"
    payload: WSUserConnectionMessagePayload


class UserLeaveMessage(BaseMessage):
    """Отключение от комнаты: топик зависит от того, лобби это или игра"""

    topic: WebSocketTopic
    message_type: Literal["UserLeave"] = "UserLeave"
    payload: WSUserConnectionMessagePayload
