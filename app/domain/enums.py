from enum import StrEnum


class Topic(StrEnum):
    """Топик WebSocket-сообщения (лобби, игра, системные сообщения)"""

    GAME = "Game"
    LOBBY = "Lobby"
    SYSTEM = "System"


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
