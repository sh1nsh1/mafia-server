from dishka import FromDishka

from domain.enums import (
    GameStageEnum,
    WebSocketMessageTypeEnum,
    WebSocketGameCommandActionTypeEnum,
)
from domain.exceptions import DomainException, PlayerDisabledException
from application.commands import GameCommand
from application.services import GameService, GameManagerService
from infrastructure.websocket import WebSocketManager
from infrastructure.logger_config import get_logger
from infrastructure.websocket.messages import (
    GameMessage,
    WSGameInfoPayload,
    WSGameCommandPayload,
)
from presentation.api.v1.dtos.requests import CurrentUser


logger = get_logger(f"{__name__}.GameWebSocketMessageHandler")


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

    async def handle(self, message: GameMessage, current_user: CurrentUser):
        """
        Обрабатывает Websocket Message взависимости от его типа
        """
        if message.message_type == WebSocketMessageTypeEnum.COMMAND:
            if not isinstance(message.payload, WSGameCommandPayload):
                raise DomainException("Неожиданный payload игровой команды")
            ws_command = message.payload
            game_command = GameCommand(
                actor_id=current_user.id,
                room_id=ws_command.room_id,
                target_id=ws_command.target_id,
            )
            game = await self._game_service.get_game_by_id(ws_command.room_id)

            # R O L E   A C T I O N
            if (
                ws_command.action_type
                == WebSocketGameCommandActionTypeEnum.ROLE_ACTION
            ):
                try:
                    if game.game_stage != GameStageEnum.NIGHT:
                        raise DomainException("Неожиданное сообщение")
                    result = await self._game_service.process_role_action(
                        game_command
                    )
                except DomainException as e:
                    logger.info(
                        f"Domain Exception from user {current_user.id} "
                        f"in room {ws_command.room_id}: {e.args}"
                    )
                    await self._websocket_manager.send_to_one(
                        GameMessage(
                            message_type=WebSocketMessageTypeEnum.ERROR,
                            payload=WSGameInfoPayload(
                                text=e.message or "Неизвестная ошибка"
                            ),
                        ),
                        ws_command.room_id,
                        current_user.id,
                    )
                    result = None

                await self._game_manager.set_event(
                    ws_command.room_id,
                    f"{ws_command.action_type}|"
                    f"{result if isinstance(result, bool) else ''}",
                )

            # V O T E
            elif (
                ws_command.action_type
                == WebSocketGameCommandActionTypeEnum.VOTE
            ):
                try:
                    if game.game_stage != GameStageEnum.DAY_VOTE:
                        raise DomainException("Неожиданное сообщение")
                    await self._game_service.process_vote(game_command)
                    target_id = str(ws_command.target_id)

                except DomainException as e:
                    logger.info(
                        f"Domain Exception from user {current_user.id} "
                        f"in room {ws_command.room_id}: {e.args}"
                    )
                    await self._websocket_manager.send_to_one(
                        GameMessage(
                            message_type=WebSocketMessageTypeEnum.ERROR,
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

            # E N D   T A L K
            elif (
                ws_command.action_type
                == WebSocketGameCommandActionTypeEnum.END_TALK
            ):
                if game.game_stage in (
                    GameStageEnum.DAY_TALK,
                    GameStageEnum.DAY_INTRO,
                ):
                    await self._game_manager.set_event(
                        ws_command.room_id, ws_command.action_type
                    )

            elif (
                ws_command.action_type
                == WebSocketGameCommandActionTypeEnum.LEAVE
            ):
                await self._game_manager.set_event(
                    ws_command.room_id,
                    f"{ws_command.action_type}|{str(current_user.id)}",
                )
                await self._websocket_manager.disconnect(
                    ws_command.room_id, current_user.id
                )
