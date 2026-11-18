from typing import Literal

from domain.enums import WebSocketTopic

from .base_message import BaseMessage, GameMessage, LobbyMessage
from .responses.game_data_payload import GameDataPayload
from .responses.game_info_payload import GameInfoPayload
from .responses.game_role_payload import GameRolePayload
from .responses.lobby_data_payload import LobbyDataPayload
from .responses.game_new_stage_payload import GameNewStagePayload
from .responses.game_action_request_payload import (
    GameActionRequestPayload,
)
from .responses.user_connection_message_payload import (
    UserConnectionMessagePayload,
)


class GameInfoMessage(GameMessage):
    message_type: Literal["Info"] = "Info"
    payload: GameInfoPayload


class GameEventMessage(GameMessage):
    message_type: Literal["Event"] = "Event"
    payload: GameInfoPayload


class GameStartMessage(GameMessage):
    message_type: Literal["GameStart"] = "GameStart"
    payload: GameInfoPayload


class GameFinishMessage(GameMessage):
    message_type: Literal["GameFinish"] = "GameFinish"
    payload: GameInfoPayload


class GameActionRequestMessage(GameMessage):
    message_type: Literal["ActionRequest"] = "ActionRequest"
    payload: GameActionRequestPayload


class GameRoleMessage(GameMessage):
    message_type: Literal["Role"] = "Role"
    payload: GameRolePayload


class GameNewStageMessage(GameMessage):
    message_type: Literal["NewStage"] = "NewStage"
    payload: GameNewStagePayload


class GameDataMessage(GameMessage):
    message_type: Literal["GameData"] = "GameData"
    payload: GameDataPayload


class LobbyDataMessage(LobbyMessage):
    message_type: Literal["LobbyData"] = "LobbyData"
    payload: LobbyDataPayload


class ErrorMessage(BaseMessage):
    """Ошибка может прийти в любом топике (Game, Lobby, System)"""

    topic: WebSocketTopic
    message_type: Literal["Error"] = "Error"
    payload: GameInfoPayload


class UserConnectMessage(BaseMessage):
    """Подключение к комнате: топик зависит от того, лобби это или игра"""

    topic: WebSocketTopic
    message_type: Literal["UserConnect"] = "UserConnect"
    payload: UserConnectionMessagePayload


class UserLeaveMessage(BaseMessage):
    """Отключение от комнаты: топик зависит от того, лобби это или игра"""

    topic: WebSocketTopic
    message_type: Literal["UserLeave"] = "UserLeave"
    payload: UserConnectionMessagePayload
