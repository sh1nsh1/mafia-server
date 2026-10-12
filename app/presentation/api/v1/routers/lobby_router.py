from dishka import FromDishka
from fastapi import HTTPException
from fastapi.routing import APIRouter
from dishka.integrations.fastapi import inject

from domain.exceptions import DomainException
from application.commands import LobbyJoinCommand, LobbyLeaveCommand, LobbyCreateCommand
from application.services import LobbyService
from presentation.api.v1.dtos.requests import CurrentUser, LobbyCreate
from presentation.api.v1.dtos.responses import LobbyLeaveResponse


lobby_router = APIRouter(prefix="/lobbies", tags=["lobby"])


@lobby_router.get("/")
@inject
async def get_all_lobbies(
    lobby_service: FromDishka[LobbyService],
):
    lobbies = await lobby_service.get_all()
    return lobbies


@lobby_router.post("/")
@inject
async def create_lobby(
    req: LobbyCreate,
    lobby_service: FromDishka[LobbyService],
    current_user: FromDishka[CurrentUser],
):
    lobby_command = LobbyCreateCommand(req.max_players, current_user.id)
    result = await lobby_service.create_lobby(lobby_command)
    return result


@lobby_router.get("/{lobby_id}")
@inject
async def get_lobby_by_id(
    lobby_id: str,
    current_user: FromDishka[CurrentUser],
    lobby_service: FromDishka[LobbyService],
):
    result = await lobby_service.get_lobby(lobby_id)
    return result


# @lobby_router.post("/{lobby_id}/join")
# @inject
# async def join_lobby(
#     lobby_id: str,
#     current_user: FromDishka[CurrentUser],
#     lobby_service: FromDishka[LobbyService],
# ):
#     command = LobbyJoinCommand(lobby_id, current_user.id)
#     try:
#         return await lobby_service.join_lobby(command)
#     except DomainException as e:
#         raise HTTPException(405, e.message)


# @lobby_router.post("/{lobby_id}/leave")
# @inject
# async def leave_lobby(
#     lobby_id: str,
#     current_user: FromDishka[CurrentUser],
#     lobby_service: FromDishka[LobbyService],
# ):
#     command = LobbyLeaveCommand(lobby_id=lobby_id, user_id=current_user.id)
#     try:
#         await lobby_service.leave_lobby(command)
#         return LobbyLeaveResponse(
#             status="OK",
#             message="User successfuly left the lobby",
#             lobby_id=lobby_id,
#         )
#     except DomainException as e:
#         raise HTTPException(405, e.message)
