from dishka import FromDishka
from fastapi import HTTPException

from application.commands import (
    LobbyJoinCommand,
    LobbyLeaveCommand,
    LobbyCreateCommand,
)
from infrastructure.logger import get_logger
from infrastructure.redis.repositories import (
    LobbyRepository,
)
from presentation.api.v1.dtos.responses.user_response import UserResponse
from presentation.api.v1.dtos.responses.lobby_response import (
    LobbyResponse,
)


logger = get_logger(f"{__name__}.LobbyService", 20)


class LobbyService:
    def __init__(self, repository: FromDishka[LobbyRepository]):
        self._lobby_repository = repository

    async def create_lobby(self, command: LobbyCreateCommand):
        lobby = await self._lobby_repository.create_lobby(
            command.admin_id, command.max_players
        )

        logger.info(f"User {lobby.admin.id} подключен к лобби {lobby.id}")

        return LobbyResponse(
            status="OK",
            id=lobby.id,
            admin_id=lobby.admin.id,
            max_players=lobby.max_players,
            participants=[
                UserResponse(id=user.id, name=user.username, email=user.email)
                for user in lobby.participants
            ],
        )

    # async def join_lobby(self, lobby_id: str, user_id: int):
    async def join_lobby(self, command: LobbyJoinCommand):
        updated_lobby = await self._lobby_repository.add_participant(
            command.lobby_id, command.user_id
        )
        logger.info(f"User {command.user_id} подключен к лобби {command.lobby_id}")
        return LobbyResponse(
            status="OK",
            id=updated_lobby.id,
            admin_id=updated_lobby.admin.id,
            max_players=updated_lobby.max_players,
            participants=[
                UserResponse(id=user.id, name=user.username, email=user.email)
                for user in updated_lobby.participants
            ],
        )

    async def get_all(self) -> list[LobbyResponse]:
        lobbies = await self._lobby_repository.get_all()
        responses: list[LobbyResponse] = []
        logger.debug(len(lobbies))
        for lobby in lobbies:
            if lobby is None:
                continue

            response = LobbyResponse(
                status="OK",
                id=lobby.id,
                admin_id=lobby.admin.id,
                max_players=lobby.max_players,
                participants=[
                    UserResponse(id=user.id, name=user.username, email=user.email)
                    for user in lobby.participants
                ],
            )

            responses.append(response)

        return responses

    async def get_lobby(self, lobby_id: str):
        lobby = await self._lobby_repository.get_lobby_by_id(lobby_id)
        print("LobbyAService.get_lobby")
        if lobby:
            return LobbyResponse(
                status="OK",
                id=lobby.id,
                admin_id=lobby.admin.id,
                max_players=lobby.max_players,
                participants=[
                    UserResponse(id=user.id, name=user.username, email=user.email)
                    for user in lobby.participants
                ],
            )
        else:
            raise HTTPException(404, "Lobby not found")

    async def leave_lobby(self, command: LobbyLeaveCommand):
        logger.debug("leave_lobby")
        await self._lobby_repository.remove_participant(
            command.lobby_id, command.user_id
        )
