from typing import Literal

from domain.enums import Topic

from .base_message import BaseMessage
from .message_type import MessageType
from .payloads.game_data_payload import GameDataPayload
from .payloads.game_info_payload import GameInfoPayload
from .payloads.game_role_payload import GameRolePayload
from .payloads.lobby_data_payload import LobbyDataPayload
from .payloads.game_new_stage_payload import GameNewStagePayload
from .payloads.user_connection_payload import (
    UserConnectionPayload,
)
from .payloads.game_action_request_payload import (
    GameActionRequestPayload,
)


class GameInfoMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.INFO] = MessageType.INFO
    payload: GameInfoPayload


class GameEventMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.EVENT] = MessageType.EVENT
    payload: GameInfoPayload


class GameStartMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.GAME_START] = MessageType.GAME_START
    payload: GameInfoPayload


class GameFinishMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.GAME_FINISH] = MessageType.GAME_FINISH
    payload: GameInfoPayload


class GameActionRequestMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.ACTION_REQUEST] = (
        MessageType.ACTION_REQUEST
    )
    payload: GameActionRequestPayload


class GameRoleMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.ROLE] = MessageType.ROLE
    payload: GameRolePayload


class GameNewStageMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.NEW_STAGE] = MessageType.NEW_STAGE
    payload: GameNewStagePayload


class GameDataMessage(BaseMessage):
    topic: Literal[Topic.GAME] = Topic.GAME
    message_type: Literal[MessageType.GAME_DATA] = MessageType.GAME_DATA
    payload: GameDataPayload


class LobbyDataMessage(BaseMessage):
    topic: Literal[Topic.LOBBY] = Topic.LOBBY
    message_type: Literal[MessageType.LOBBY_DATA] = MessageType.LOBBY_DATA
    payload: LobbyDataPayload


class ErrorMessage(BaseMessage):
    """Ошибка, которая может прийти в любом топике"""

    topic: Topic
    message_type: Literal[MessageType.ERROR] = MessageType.ERROR
    payload: GameInfoPayload


class UserConnectMessage(BaseMessage):
    """Подключение к комнате: топик зависит от того, лобби это или игра"""

    topic: Topic
    message_type: Literal[MessageType.USER_CONNECT] = MessageType.USER_CONNECT
    payload: UserConnectionPayload


class UserLeaveMessage(BaseMessage):
    """Отключение от комнаты: топик зависит от того, лобби это или игра"""

    topic: Topic
    message_type: Literal[MessageType.USER_LEAVE] = MessageType.USER_LEAVE
    payload: UserConnectionPayload
