from enum import StrEnum
from typing import Literal


WebSocketTopic = Literal["Game", "Lobby", "System"]
"""Топик WebSocket-сообщения (лобби, игра, системные сообщения)"""


class TeamEnum(StrEnum):
    NONE = "None"
    # Classic mode
    CITIZEN_TEAM = "CitizenTeam"
    MAFIA_TEAM = "MafiaTeam"

    # TODO Extended mode
    NEUTRAL = "Neutral"


class RoleEnum(StrEnum):
    # Sport mode
    CITIZEN = "Citizen"
    MAFIA_MEMBER = "MafiaMember"
    SHERIFF = "Sheriff"

    # Amateur mode
    DOCTOR = "Doctor"
    MAFIA_DON = "MafiaDon"
    PROSTITUTE = "Prostitute"

    # Extended mode
    MANIAC = "Maniac"
    DEPUTY_SHERIFF = "DeputySheriff"
    SHAPESHIFTER = "Shapeshifter"


class GameStatusEnum(StrEnum):
    IN_PROGRESS = "In progress"
    PAUSED = "Paused"
    FINISHED = "Finished"


class GameStageEnum(StrEnum):
    DAY_INTRO = "DayIntro"
    DAY_TALK = "DayTalk"
    DAY_VOTE = "DayVote"
    NIGHT = "Night"


class WebSocketMessageTypeEnum(StrEnum):
    """WebSocket message type"""

    COMMAND = "Command"

    ERROR = "Error"  # WebSocketGameInfoPayload
    INFO = "Info"  # WebSocketGameInfoPayload

    EVENT = "Event"

    NEW_STAGE = "NewStage"  # WebSocketGameNewStagePayload

    GAME_DATA = "GameData"  # WebSocketGameGameDataPayload

    LOBBY_DATA = "LobbyData"

    ACTION_REQUEST = "ActionRequest"  # WebSocketGameActionRequestPayload

    USER_CONNECT = "UserConnect"  # WebSocketUserConnectionMessagePayload
    USER_LEAVE = "UserLeave"  # WebSocketUserConnectionMessagePayload

    GAME_START = "GameStart"
    GAME_FINISH = "GameFinish"

    ROLE = "Role"


class WebSocketGameCommandActionTypeEnum(StrEnum):
    VOTE = "Vote"
    ROLE_ACTION = "RoleAction"
    END_TALK = "EndTalk"
    LEAVE = "Leave"


class WebSocketLobbyCommandTypeEnum(StrEnum):
    KICK = "Kick"
    START = "Start"
    DELETE = "Delete"
    LEAVE = "Leave"


class PlayerStatusEnum(StrEnum):
    RAIDED = "Raided"  # by mafia
    ASSAULTED = "Assaulted"  # by maniac
    HEALED = "Healed"  # by doctor
    DISABLED = "Disabled"  # by prostitute

    HEALED_PREV = "HealedPrev"  # for doctor check
    DISABLED_PREV = "DisabledPrev"  # for prostitute check

    ACTED = "Acted"  # if role action performed

    UNTARGETABLE = "Untargetable"
