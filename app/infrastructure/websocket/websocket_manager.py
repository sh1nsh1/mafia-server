import asyncio
from uuid import UUID
from collections.abc import Callable, Awaitable

from fastapi import WebSocket

from domain.enums import WebSocketMessageTypeEnum
from domain.exceptions import AppException
from infrastructure.logger import get_logger
from infrastructure.websocket.dtos import WebSocketMessage
from infrastructure.websocket.room_connection import RoomConnection


logger = get_logger(f"{__name__}.WebSocketManager", 20)


class WebSocketManager:
    _instance = None

    active_connections: dict[str, dict[UUID, RoomConnection]]
    """room_id -> {user_id -> websocket}"""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.active_connections = {}

    async def get_room_connection(
        self, room_id: str, user_id: UUID
    ) -> RoomConnection | None:
        logger.debug("get_room_connection")
        room_connections = self.active_connections.get(room_id)
        if not room_connections:
            return None
        connection = room_connections.get(user_id)
        return connection

    async def connect(self, ws: WebSocket, room_id: str, user_id: UUID):
        logger.debug("connect")

        await ws.accept()

        connection = await self.get_room_connection(room_id, user_id)
        # первое подключение
        if not connection:
            connection = RoomConnection(ws, asyncio.Queue())
            # если подключие админа
            if room_id not in self.active_connections:
                self.active_connections[room_id] = {}

            self.active_connections[room_id][user_id] = connection
        # повторное подключение
        else:
            connection.websocket = ws
            await self.handle_reconnect(connection, room_id, user_id)

    async def handle_disconnect(
        self, room_id: str, user_id: UUID
    ) -> RoomConnection | None:
        logger.debug("handle_disconnect")
        connection = await self.get_room_connection(room_id, user_id)
        if not connection:
            logger.warning("handle_disconnect: подключения не существует")
            return None

        connection.is_disconnected = True
        return connection

    async def disconnect(self, room_id: str, user_id: UUID):
        logger.debug("disconnect")
        connection = await self.handle_disconnect(room_id, user_id)
        if connection:
            await connection.websocket.close()

    async def delete_all_connections(self, room_id: str):
        logger.debug("disconnect_all")
        room_connections = self.active_connections[room_id]

        for connection in room_connections.values():
            await connection.websocket.close(reason="Комната удалена владельцем лобби")

        del self.active_connections[room_id]

    async def send_to_one(self, message: WebSocketMessage, room_id: str, user_id: UUID):
        """
        Отправить message игроку user_id в комнате room_id
        """
        logger.debug("send_to_one")
        logger.info("\n".join([f"{k}:\t{v}" for k, v in message.model_dump().items()]))
        connection = await self.get_room_connection(room_id, user_id)
        if not connection:
            exc = AppException("Подключения не существует")
            logger.error(exc)
            raise exc

        if connection.is_disconnected:
            logger.info("enqueue")
            await connection.message_queue.put(message)
        else:
            logger.info("send")
            await connection.websocket.send_json(message.model_dump_json(by_alias=True))

    async def send_to_many(
        self, message: WebSocketMessage, room_id: str, user_ids: list[UUID]
    ):
        logger.debug("send_to_many")
        for user_id in user_ids:
            await self.send_to_one(message, room_id, user_id)

    async def send_broadcast(self, message: WebSocketMessage, room_id: str):
        logger.debug("send_broadcast")
        room_connections = self.active_connections.get(room_id)
        if not room_connections:
            logger.debug(f"send_broadcast: нет подключений в комнате {room_id}")
            return
        all_users = list(room_connections.keys())
        logger.debug(all_users)
        await self.send_to_many(message, room_id, all_users)

    async def set_callback(
        self,
        room_id: str,
        user_id: UUID,
        callback: Callable[[str, UUID], Awaitable[None]],
    ):
        connection = await self.get_room_connection(room_id, user_id)
        if not connection:
            logger.error("Невозможно применить callback к подключению")
            return
        connection.send_state_message = callback
        connection.is_callback_set = True

    async def handle_reconnect(
        self,
        connection: RoomConnection,
        room_id: str,
        user_id: UUID,
    ):
        if connection.is_callback_set:
            # отправить данные об игре вне очереди
            connection.is_disconnected = False
            await connection.send_state_message(room_id, user_id)
            connection.is_disconnected = True

        while not connection.message_queue.empty():
            message: WebSocketMessage = connection.message_queue.get_nowait()
            # во время отправки сообщения разблокировать получение
            connection.is_disconnected = False
            if not connection.is_callback_set:
                await self.send_to_one(message, room_id, user_id)

            elif message.message_type in [WebSocketMessageTypeEnum.ACTION_REQUEST]:
                connection.last_action_request_message = message

            connection.is_disconnected = True

            connection.message_queue.task_done()

        connection.is_disconnected = False
        if connection.last_action_request_message:
            await self.send_to_one(
                connection.last_action_request_message, room_id, user_id
            )

    async def clear_last_action_request_message(self, room_id: str, user_id: UUID):
        connecton = await self.get_room_connection(room_id, user_id)
        if not connecton:
            return
        connecton.last_action_request_message = None
