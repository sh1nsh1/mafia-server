from datetime import datetime

from dishka import FromDishka, AsyncContainer
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter
from starlette.websockets import WebSocketState
from dishka.integrations.fastapi import inject

from domain.enums import WebSocketTopicEnum, WebSocketMessageTypeEnum
from domain.exceptions import DomainException
from application.services import SecurityService, RoomWebSocketService
from infrastructure.logger import get_logger
from infrastructure.websocket.dtos import (
    WebSocketMessage,
    WSGameInfoPayload,
)


room_websocket_router = APIRouter()
logger = get_logger(__name__, 10)


@room_websocket_router.websocket("/rooms/{room_id}")
@inject
async def room_websocket(
    room_id: str, websocket: WebSocket, container: FromDishka[AsyncContainer]
):
    logger.debug("room_websocket")
    token = websocket.headers.get("authorization", "").removeprefix("Bearer ")

    if not token:
        token = websocket.query_params.get("authorization", "").removeprefix("Bearer ")

    current_user = None
    subscribed = False
    try:
        async with container() as request_container:
            security_service = await request_container.get(SecurityService)
            current_user = await security_service.get_current_user(token)

        async with container() as request_container:
            room_websocket_service = await request_container.get(RoomWebSocketService)
            await room_websocket_service.subscribe_room_webscoket(
                room_id, current_user, websocket
            )
        subscribed = True

        while websocket.application_state == WebSocketState.CONNECTED:
            raw_message: dict[str, any] = await websocket.receive_json()
            logger.debug(f"{raw_message} {type(raw_message)}")
            ws_message = WebSocketMessage(**raw_message)
            try:
                async with container() as request_container:
                    room_service = await request_container.get(RoomWebSocketService)
                    await room_service.handle_message(ws_message, current_user)

            except DomainException as e:
                logger.error(
                    f"Error on handling message: {ws_message.model_dump()}\n"
                    f"Error: {e.args}"
                )
                await websocket.send_text(
                    WebSocketMessage(
                        message_type=WebSocketMessageTypeEnum.ERROR,
                        topic=WebSocketTopicEnum(e.topic),
                        timestamp=datetime.now().isoformat(),
                        payload=WSGameInfoPayload(text=e.message),
                    ).model_dump_json(by_alias=True)
                )

    except WebSocketDisconnect:
        username = current_user.username if current_user else ""
        logger.info(f"{username} разорвал соединение с комнатой {room_id}")

    finally:
        # Очистка должна выполняться при любом выходе (disconnect, отмена задачи,
        # исключение во время подписки), иначе лобби/участники остаются в Redis.
        if subscribed and current_user is not None:
            try:
                async with container() as request_container:
                    room_service = await request_container.get(RoomWebSocketService)
                    await room_service.unsubscribe_room_webscoket(room_id, current_user)
            except Exception as e:
                logger.error(f"Error on unsubscribe: {e.args}")
