from typing import Literal

from domain.enums import WebSocketTopic


class AppException(Exception):
    """
    Базовое исключение приложения
    """

    def __init__(self, message: str = "An unknown error occurred"):
        self.message = message
        super().__init__(message)


class DomainException(AppException):
    """
    Исключение доменной логики
    """

    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        message: str = "Произошла неизвестная ошибка",
        *,
        topic: WebSocketTopic | None = None,
    ):
        if topic is not None:
            self.topic = topic
        super().__init__(message)


class TokenException(AppException):
    """
    Исключение access или refresh токенов
    """

    def __init__(
        self,
        expected_token: Literal["access", "refresh"],
        message: str = "An unknow error with token provided",
    ):
        self.expected_token = expected_token
        super().__init__(message)


class RepoException(AppException):
    """
    Исключение инфраструктурного слоя
    """

    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        message: str = "Неизвестная ошибка в репозитории",
        context_id: str | None = None,
        user_id: str | None = None,
        *,
        topic: WebSocketTopic | None = None,
    ):
        if topic is not None:
            self.topic = topic
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message)


class UnexpectedWebSocketMessageActionType(DomainException):
    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        provided: str | None = None,
        expected: str | None = None,
    ):
        message: str = (
            f"Неверный ActionType: получен {provided}, ожидался {expected}"
        )
        super().__init__(message)


class PlayerDisabledException(DomainException):
    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        message: str = "Ваше действие заблокировано",
    ):
        super().__init__(message)


class VotedDisabledTargetException(DomainException):
    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        message: str = "Невозможно проголосовать за выбранного игрока",
    ):
        super().__init__(message)


class VotedUntargetableException(DomainException):
    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        message: str = "Запрещено голосовать за этого игрока",
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message)


class PlayerChosenTwiceException(DomainException):
    topic: WebSocketTopic = "Game"

    def __init__(
        self,
        message: str = "Запрещается выбирать игрока две ночи подряд",
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message)


class RoomNotFoundException(DomainException):
    topic: WebSocketTopic = "Lobby"

    def __init__(
        self,
        message: str | None = None,
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        message = message or f"Лобби {context_id} не найдено"
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message)


class UserAlredyInLobbyException(DomainException):
    topic: WebSocketTopic = "Lobby"

    def __init__(
        self,
        message: str | None = None,
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        message = message or f"Пользователь {user_id} уже в лобби {context_id}"
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message)


class ActionAlreadyPerformedException(RepoException):
    topic: WebSocketTopic = "Lobby"

    def __init__(
        self,
        message: str | None = None,
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        message = message or (
            f"Конкурентное действие пользователя {user_id} в лобби {context_id}"
        )
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message, context_id, user_id)


class LobbyIsFullException(DomainException):
    topic: WebSocketTopic = "Lobby"

    def __init__(
        self,
        message: str | None = None,
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        message = message or (
            f"Пользователь {user_id} не может войти в полное лобби {context_id}"
        )
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message)


class UserNotInLobbyException(RepoException):
    topic: WebSocketTopic = "Lobby"

    def __init__(
        self,
        message: str | None = None,
        context_id: str | None = None,
        user_id: str | None = None,
    ):
        message = message or f"Пользователя {user_id} нет в лобби {context_id}"
        self.context_id = context_id
        self.user_id = user_id
        super().__init__(message, context_id, user_id)
