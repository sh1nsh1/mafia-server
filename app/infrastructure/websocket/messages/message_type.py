from enum import StrEnum


class MessageType(StrEnum):
    """Допустимые значения поля messageType WebSocket-сообщений"""

    COMMAND = "Command"
    INFO = "Info"
    EVENT = "Event"
    GAME_START = "GameStart"
    GAME_FINISH = "GameFinish"
    ACTION_REQUEST = "ActionRequest"
    ROLE = "Role"
    NEW_STAGE = "NewStage"
    GAME_DATA = "GameData"
    LOBBY_DATA = "LobbyData"
    ERROR = "Error"
    USER_CONNECT = "UserConnect"
    USER_LEAVE = "UserLeave"
