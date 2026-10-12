from datetime import datetime

from dishka import FromDishka

from domain.enums import (
    GameStageEnum,
    WebSocketTopicEnum,
    WebSocketMessageTypeEnum,
    WebSocketGameCommandActionTypeEnum,
)
from domain.exceptions import DomainException, PlayerDisabledException
from application.services import GameService, GameManagerService
from infrastructure.logger import get_logger
from infrastructure.websocket import WebSocketManager
from infrastructure.websocket.dtos import (
    WebSocketMessage,
    WSGameInfoPayload,
    WSGameCommandPayload,
)
from presentation.api.v1.dtos.requests import CurrentUser


logger = get_logger(f"{__name__}.GameWebSocketMessageHandler", 20)


class GameWSMessageHandler:
    def __init__(
        self,
        game_service: FromDishka[GameService],
        game_manager: FromDishka[GameManagerService],
        websocket_manager: FromDishka[WebSocketManager],
    ):
        self._game_service = game_service
        self._game_manager = game_manager
        self._websocket_manager = websocket_manager

    async def handle(self, message: WebSocketMessage, current_user: CurrentUser):
        """
        Обрабатывает Websocket Message взависимости от его типа
        """
        if message.message_type == WebSocketMessageTypeEnum.COMMAND:
            ws_command = WSGameCommandPayload(**message.payload.model_dump())
            game = await self._game_service.get_game_by_id(ws_command.room_id)
            if ws_command.action_type == WebSocketGameCommandActionTypeEnum.ROLE_ACTION:
                try:
                    if game.game_stage != GameStageEnum.NIGHT:
                        raise DomainException(
                            WebSocketTopicEnum.GAME, "Неожиданное сообщение"
                        )
                    result = await self._game_service.process_role_action(ws_command)
                except DomainException as e:
                    logger.info(
                        f"Domain Exception from user {current_user.id} "
                        "in room {websocket_command.room_id}: {e.args}"
                    )
                    await self._websocket_manager.send_to_one(
                        WebSocketMessage(
                            message_type=WebSocketMessageTypeEnum.ERROR,
                            topic=WebSocketTopicEnum(e.topic),
                            timestamp=datetime.now().isoformat(),
                            payload=WSGameInfoPayload(
                                text=e.message or "Неизвестная ошибка"
                            ),
                        ),
                        ws_command.room_id,
                        current_user.id,
                    )
                    logger.info("Сообщение об ошибке отправлено")
                    result = None

                await self._game_manager.set_event(
                    ws_command.room_id,
                    f"{ws_command.action_type}|"
                    f"{result if isinstance(result, bool) else ''}",
                )

            elif ws_command.action_type == WebSocketGameCommandActionTypeEnum.VOTE:
                try:
                    if game.game_stage != GameStageEnum.DAY_VOTE:
                        raise DomainException(
                            WebSocketTopicEnum.GAME, "Неожиданное сообщение"
                        )
                    await self._game_service.process_vote(ws_command)
                    target_id = str(ws_command.target_id)

                except DomainException as e:
                    logger.info(
                        f"Domain Exception from user {current_user.id} "
                        f"in room {ws_command.room_id}: {e.args}"
                    )
                    await self._websocket_manager.send_to_one(
                        WebSocketMessage(
                            message_type=WebSocketMessageTypeEnum.ERROR,
                            topic=WebSocketTopicEnum(e.topic),
                            timestamp=datetime.now().isoformat(),
                            payload=WSGameInfoPayload(
                                text=e.message or "Неизвестная ошибка"
                            ),
                        ),
                        ws_command.room_id,
                        current_user.id,
                    )
                    logger.debug("Сообщение об ошибке отправлено")
                    if not isinstance(e, PlayerDisabledException):
                        logger.debug("wait for another vote")
                        return
                    target_id = ""

                await self._game_manager.set_event(
                    ws_command.room_id,
                    f"{ws_command.action_type}|{target_id}",
                )
                return

            elif ws_command.action_type == WebSocketGameCommandActionTypeEnum.END_TALK:
                if game.game_stage in (GameStageEnum.DAY_TALK, GameStageEnum.DAY_INTRO):
                    await self._game_manager.set_event(
                        ws_command.room_id, ws_command.action_type
                    )

            elif ws_command.action_type == WebSocketGameCommandActionTypeEnum.LEAVE:
                await self._game_manager.set_event(
                    ws_command.room_id,
                    f"{ws_command.action_type}|{str(current_user.id)}",
                )
                await self._websocket_manager.disconnect(
                    ws_command.room_id, current_user.id
                )
