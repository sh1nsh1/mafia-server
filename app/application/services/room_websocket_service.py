from dishka import FromDishka
from fastapi import WebSocket

from domain.enums import WebSocketTopic
from application.commands import LobbyJoinCommand
from application.services import UserService, LobbyService
from infrastructure.websocket import WebSocketManager
from infrastructure.logger_config import get_logger
from application.ws_message_handlers import (
    GameWSMessageHandler,
    LobbyWSMessageHandler,
)
from infrastructure.websocket.messages import (
    IncomingMessage,
    UserLeaveMessage,
    GameCommandMessage,
    UserConnectMessage,
    LobbyCommandMessage,
    UserConnectionPayload,
)
from presentation.api.v1.dtos.requests import CurrentUser
from presentation.api.v1.dtos.responses import UserResponse, LobbyResponse


logger = get_logger(f"{__name__}.RoomWebSocketService")


class RoomWebSocketService:
    def __init__(
        self,
        websocket_manager: FromDishka[WebSocketManager],
        game_websocket_handler: FromDishka[GameWSMessageHandler],
        lobby_websocket_handler: FromDishka[LobbyWSMessageHandler],
        user_service: FromDishka[UserService],
        lobby_service: FromDishka[LobbyService],
    ):
        self._websocket_manager = websocket_manager
        self._game_websocket_handler = game_websocket_handler
        self._lobby_websocket_handler = lobby_websocket_handler
        self._user_service = user_service
        self._lobby_service = lobby_service

    async def subscribe_room_webscoket(
        self, room_id: str, current_user: CurrentUser, websocket: WebSocket
    ):
        logger.debug("subscribe_room_webscoket")

        await self._websocket_manager.connect(
            websocket, room_id, current_user.id
        )

        lobby: LobbyResponse = await self._lobby_service.join_lobby(
            LobbyJoinCommand(room_id, current_user.id)
        )

        topic: WebSocketTopic = "Lobby" if lobby else "Game"

        message = UserConnectMessage(
            topic=topic,
            payload=UserConnectionPayload(
                message=f"User {current_user.username} подключился к комнате",
                user=UserResponse(
                    id=current_user.id,
                    name=current_user.username,
                    email=current_user.email,
                ),
                lobby=lobby if lobby else None,
            ),
        )
        await self._websocket_manager.send_broadcast(message, room_id)

    async def unsubscribe_room_webscoket(
        self, room_id: str, current_user: CurrentUser
    ):
        logger.debug("unsubscribe_room_webscoket")
        await self._websocket_manager.handle_disconnect(
            room_id, current_user.id
        )

        user_joined_room = await self._user_service.get_user_joined_room(
            current_user.id
        )
        if not user_joined_room:
            logger.error("Can't unsubscribe non-existing room")
            return

        # logger.info("leave ")
        # await self._lobby_service.leave_lobby(
        #     LobbyLeaveCommand(
        #         lobby_id=room_id,
        #         user_id=current_user.id,
        #     )
        # )

        topic: WebSocketTopic = "Lobby" if user_joined_room.is_lobby else "Game"
        message = UserLeaveMessage(
            topic=topic,
            payload=UserConnectionPayload(
                message=f"User {current_user.username} покинул комнату",
                user=UserResponse(
                    id=current_user.id,
                    name=current_user.username,
                    email=current_user.email,
                ),
                lobby=None,
            ),
        )
        await self._websocket_manager.send_broadcast(message, room_id)

    async def handle_message(
        self,
        message: IncomingMessage,
        current_user: CurrentUser,
    ):
        logger.debug("handle_message")
        match message:
            case LobbyCommandMessage():
                await self._lobby_websocket_handler.handle(
                    message, current_user
                )

            case GameCommandMessage():
                await self._game_websocket_handler.handle(message, current_user)
