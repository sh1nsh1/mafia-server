import random
import asyncio
from uuid import UUID
from datetime import datetime

from dishka import FromDishka, AsyncContainer

from domain.enums import (
    RoleEnum,
    GameStageEnum,
    PlayerStatusEnum,
    WebSocketTopicEnum,
    WebSocketMessageTypeEnum,
    WebSocketGameCommandActionTypeEnum,
)
from domain.entities import Game, Player
from domain.exceptions import (
    AppException,
    DomainException,
    UnexpectedWebSocketMessageActionType,
)
from application.services import GameService
from infrastructure.logger import get_logger
from infrastructure.websocket import WebSocketManager
from infrastructure.websocket.dtos import (
    WebSocketMessage,
    WSGameDataPayload,
    WSGameInfoPayload,
    WSGameRolePayload,
    WSGameNewStagePayload,
    WSGameActionRequestPayload,
)
from presentation.api.v1.dtos.responses import PlayerResponse


logger = get_logger(f"{__name__}.GameManagerService", 20)


class GameManagerService:
    """
    Менеджер по управлению активными играми и их хранению
    """

    def __init__(
        self, container: AsyncContainer, websocket_manager: FromDishka[WebSocketManager]
    ):
        self._game_service = RequestScopedProxy(container, GameService)
        self._websocket_manager = websocket_manager

        self._active_game_loops: dict[str, asyncio.Task] = {}
        """game_id -> game_loop (Task)"""

        self._game_stage_update_listeners: dict[str, asyncio.Event] = {}
        """game_id -> game_update_listener (Event)"""

        self._game_event_listeners: dict[str, asyncio.Queue] = {}
        """game_id -> game_event_listener (Queue)"""

        self._game_night_role_aciton_orders: dict[str, list[RoleEnum]] = {}
        """game_id -> game_night_role_aciton_order (list[RoleEnum])"""

    async def start_game(self, game: Game):
        """
        Запускает Game и сохраняет её Game Loop в памяти
        """
        logger.debug(f"start_game {game.id}")
        if game.id in self._active_game_loops:
            raise AppException("Игра уже запущена")

        self._game_stage_update_listeners[game.id] = asyncio.Event()
        self._game_event_listeners[game.id] = asyncio.Queue()
        self._game_night_role_aciton_orders[
            game.id
        ] = await self._game_service.get_night_role_action_order()

        await self._websocket_manager.send_broadcast(
            WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.GAME_START,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(text="Игра началась"),
            ),
            game.id,
        )

        for player in game.players:
            await self._websocket_manager.set_callback(
                game.id, player.user.id, self.send_game_state
            )
            await self.send_game_state(game.id, player.user.id)

        self._game_stage_update_listeners[game.id].set()

        # создать Task с game loop
        task = asyncio.create_task(self._create_game_loop(game))
        self._active_game_loops[game.id] = task

        task.add_done_callback(
            lambda task: asyncio.create_task(self._on_game_loop_done(game.id, task))
        )

    async def wakeup_game_loop(self, game_id):
        logger.debug(f"emit_update_signal {game_id}")
        update_listener = self._game_stage_update_listeners.get(game_id)
        if update_listener:
            update_listener.set()
        else:
            exc = DomainException(
                topic=WebSocketTopicEnum.GAME, message=f"can't emit update on {game_id}"
            )
            logger.error(exc)
            logger.exception(exc)
            raise exc

    async def set_event(self, game_id: str, event: str):
        logger.debug(f"set_event {event} in {game_id}")
        event_listener = self._game_event_listeners.get(game_id)
        logger.debug(f"listeners {event_listener} {event}")
        if event_listener:
            await event_listener.put(event)
        else:
            exc = DomainException(
                topic=WebSocketTopicEnum.GAME, message=f"can't create event {event}"
            )
            logger.exception(exc)
            raise exc

    async def _create_game_loop(self, game: Game) -> None:
        logger.debug(f"_create_game_loop {game.id}")

        """
        Создаёт Game Loop
        """
        try:
            while True:
                game = await self._game_service.get_game_by_id(game.id)
                # если игра завершилась
                if await game.check_finish_condition():
                    if not game.winner_team:
                        logger.error("Победитель не установлен")
                        exc = DomainException(
                            message="Победитель не установлен",
                            topic=WebSocketTopicEnum.GAME,
                        )
                        logger.exception(exc)
                        raise exc
                    game_end_message = WebSocketMessage(
                        message_type=WebSocketMessageTypeEnum.GAME_FINISH,
                        topic=WebSocketTopicEnum.GAME,
                        timestamp=datetime.now().isoformat(),
                        payload=WSGameInfoPayload(
                            text=f"Игра окончилась победой {game.winner_team.value}",
                        ),
                    )
                    await self._websocket_manager.send_broadcast(
                        game_end_message, game.id
                    )
                    return

                logger.debug(f"game stage: {game.game_stage}")
                stage_update_listener = self._game_stage_update_listeners[game.id]
                try:
                    await asyncio.wait_for(
                        stage_update_listener.wait(), timeout=60 * 60
                    )
                    logger.debug("catch update")
                    stage_update_listener.clear()

                    match game.game_stage:
                        case GameStageEnum.DAY_INTRO:
                            game = await self._game_service.get_game_by_id(game.id)
                            message = f"Знакомство {game.game_stage.value}"

                            await self.announce_new_stage(
                                game.id, GameStageEnum.DAY_INTRO, message
                            )

                            await self.show_roles(game)

                            await self.conduct_day_talk_stage(game.id, 30)

                        case GameStageEnum.NIGHT:
                            game = await self._game_service.get_game_by_id(game.id)
                            message = f"Город засыпаает {game.game_stage.value}"

                            await self.announce_new_stage(
                                game.id, GameStageEnum.NIGHT, message
                            )

                            await self.conduct_night_stage(game.id)

                        case GameStageEnum.DAY_TALK:
                            game = await self._game_service.get_game_by_id(game.id)
                            message = f"День {game.round_count} Общение {game.game_stage.value}"
                            await self.announce_new_stage(
                                game.id, GameStageEnum.DAY_TALK, message
                            )

                            await self.conduct_day_talk_stage(game.id)

                        case GameStageEnum.DAY_VOTE:
                            game = await self._game_service.get_game_by_id(game.id)
                            message = f"День {game.round_count} Голосование {game.game_stage.value}"
                            await self.announce_new_stage(
                                game.id, GameStageEnum.DAY_VOTE, message
                            )

                            await self.conduct_day_vote_stage(game.id)

                # таймаут если в игре не было активных действий
                except TimeoutError:
                    logger.error("GAMELOOP timeout")
                    raise

        except asyncio.CancelledError as e:
            logger.info(e)
            raise

        except Exception as e:
            logger.error(e)
            logger.exception(e)
            logger.error("G A M E L O O P    E R R O R")
            raise

    async def _on_game_loop_done(self, game_id: str, task: asyncio.Task):
        """
        Обрабатывает конец игры
        """
        logger.info("on gameloop done")
        try:
            if task.cancelled():
                logger.info(f"Game {game_id} was externally cancelled")
            # Проверяем не было ли исключения
            if exc := task.exception():
                if isinstance(exc, TimeoutError):
                    logger.info(f"Game {game_id} was abandoned due to timeout")
                elif isinstance(exc, DomainException):
                    logger.error(f"Game {game_id} domain error: {exc}")
            if task.done():
                logger.info(f"Game {game_id} succesfully finished")

            # Удаляем из активных игр
            logger.info("del game loop")
            self._active_game_loops.pop(game_id, None)
            logger.info("del game loop - DONE")

            logger.info("del update listener")
            self._game_stage_update_listeners.pop(game_id, None)
            logger.info("del update listener - DONE")

            logger.info("del event listener")
            self._game_event_listeners.pop(game_id, None)
            logger.info("del update listener - DONE")

            logger.info("del action order")
            self._game_night_role_aciton_orders.pop(game_id, None)
            logger.info("del action order - DONE")

            logger.info("del game data")
            await self._game_service.delete_game(game_id)
            logger.info("del game data - DONE")

            logger.info(f"Game {game_id} loop successfully cleaned up")
        except Exception as e:
            logger.error("Error on finishing game")
            logger.exception(e)
        finally:
            logger.info(f"Game process {game_id} finished")

    async def conduct_day_talk_stage(self, game_id: str, talk_timeout: int = 90):
        logger.debug(f"conduct_day_talk_stage {game_id}")

        # получить свежее состояние игры
        game = await self._game_service.get_game_by_id(game_id)
        logger.debug(
            f"conduct_day_vote_stage: {[f'{player.user.username} {player.is_alive}' for player in game.players]}"
        )

        # определить порядок речей
        talk_order = await self._get_talk_order(game)
        for i in talk_order:
            if not game.players[i].is_alive:
                continue

            logger.debug(
                f"talks {game.players[i].user.username} {game.players[i].is_alive}"
            )
            talk_event_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.EVENT,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(
                    text=f"Говорит игрок {game.players[i].user.username}",
                ),
            )
            await self._websocket_manager.send_broadcast(
                talk_event_message,
                game.id,
            )
            action_request_message = talk_event_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.ACTION_REQUEST,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameActionRequestPayload(
                    text="Ваша очередь говорить", timeout=talk_timeout
                ),
            )
            await self._websocket_manager.send_to_one(
                action_request_message, game.id, game.players[i].user.id
            )
            logger.debug(f"invite sent to {game.players[i].user.id}")
            event_listener = self._game_event_listeners[game.id]
            try:
                event, _ = await asyncio.wait_for(
                    self.wait_for_event(
                        event_listener=event_listener,
                        expected_event=WebSocketGameCommandActionTypeEnum.END_TALK,
                    ),
                    timeout=talk_timeout,
                )
                if event == WebSocketGameCommandActionTypeEnum.LEAVE:
                    await self._game_service.leave_game(
                        game.id, game.players[i].user.id
                    )
                    logger.debug(event_listener)

                elif event != WebSocketGameCommandActionTypeEnum.END_TALK:
                    exc = UnexpectedWebSocketMessageActionType(
                        provided=event,
                        expected=WebSocketGameCommandActionTypeEnum.END_TALK,
                    )
                    logger.error(exc)
                    raise exc

            except TimeoutError:
                logger.warning(
                    f"Игрок {game.players[i].user.username} закончил говорить (timeout)"
                )
            finally:
                talk_end_message = WebSocketMessage(
                    message_type=WebSocketMessageTypeEnum.EVENT,
                    topic=WebSocketTopicEnum.GAME,
                    timestamp=datetime.now().isoformat(),
                    payload=WSGameInfoPayload(
                        text=f"Игрок {game.players[i].user.username} закончил говорить"
                    ),
                )
                await self._websocket_manager.send_broadcast(talk_end_message, game.id)
        for player in game.players:
            await self._websocket_manager.clear_last_action_request_message(
                game.id, player.user.id
            )
        game = await self._game_service.proceed_next_stage(game)
        logger.info(str(game))
        await self.wakeup_game_loop(game.id)

    async def conduct_night_stage(self, game_id: str, turn_timeout=120):
        logger.debug(f"conduct_night_stage {game_id}")
        game = await self._game_service.get_game_by_id(game_id)

        player_role_groups = await self._game_service.get_night_action_player_groups(
            game
        )
        action_order = self._game_night_role_aciton_orders[game_id]
        for role_name in action_order:
            if role_name not in player_role_groups:
                logger.debug(f"{role_name} not in game {game_id}. skiping")
                continue

            # Broadcast message
            role_action_websocket_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.INFO,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(text=f"Ход {role_name.value}"),
            )
            await self._websocket_manager.send_broadcast(
                role_action_websocket_message, game_id
            )

            # only actor send message
            player_group = player_role_groups[role_name]
            role_action_websocket_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.ACTION_REQUEST,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameActionRequestPayload(
                    text="Выберите свою цель", timeout=turn_timeout
                ),
            )
            await self._websocket_manager.send_to_many(
                role_action_websocket_message,
                game_id,
                [actor.user.id for actor in player_group],
            )

            event_listener = self._game_event_listeners[game_id]
            try:
                (event_type, extra_data) = await asyncio.wait_for(
                    self.wait_for_event(
                        event_listener=event_listener,
                        expected_event=WebSocketGameCommandActionTypeEnum.ROLE_ACTION,
                    ),
                    timeout=turn_timeout,
                )

                if (
                    event_type == WebSocketGameCommandActionTypeEnum.LEAVE
                    and extra_data
                ):
                    await self._game_service.leave_game(game.id, UUID(extra_data))

                if extra_data:
                    result_message = WebSocketMessage(
                        message_type=WebSocketMessageTypeEnum.INFO,
                        topic=WebSocketTopicEnum.GAME,
                        timestamp=datetime.now().isoformat(),
                        payload=WSGameInfoPayload(
                            text=f"Результат проверки: {extra_data}"
                        ),
                    )
                    await self._websocket_manager.send_to_many(
                        result_message,
                        game_id,
                        [actor.user.id for actor in player_group],
                    )
                    logger.debug(event_listener)

            except TimeoutError:
                logger.debug("RoleAction Timeout")

            finally:
                action_finish_message = WebSocketMessage(
                    message_type=WebSocketMessageTypeEnum.INFO,
                    topic=WebSocketTopicEnum.GAME,
                    timestamp=datetime.now().isoformat(),
                    payload=WSGameInfoPayload(
                        text=f"Конец хода {role_name}. {role_name} засыпает"
                    ),
                )
                await self._websocket_manager.send_broadcast(
                    action_finish_message, game.id
                )

        game = await self._game_service.get_game_by_id(game_id)
        died_players = await game.resolve_night_stage()

        game = await self._game_service.save_game(game)
        if died_players:
            text = f"Ночью из игры выбыли: {', '.join([player.user.username for player in died_players])}"
        else:
            text = "Ночью никто не выбыл"
        died_players_message = WebSocketMessage(
            message_type=WebSocketMessageTypeEnum.EVENT,
            topic=WebSocketTopicEnum.GAME,
            timestamp=datetime.now().isoformat(),
            payload=WSGameInfoPayload(text=text),
        )
        await self._websocket_manager.send_broadcast(died_players_message, game.id)

        died_personal_message = WebSocketMessage(
            message_type=WebSocketMessageTypeEnum.EVENT,
            topic=WebSocketTopicEnum.GAME,
            timestamp=datetime.now().isoformat(),
            payload=WSGameInfoPayload(text="Вы выбыли этой ночью"),
        )
        await self._websocket_manager.send_to_many(
            died_personal_message, game.id, [player.user.id for player in died_players]
        )
        game = await self._game_service.proceed_next_stage(game)

        logger.debug(
            f"after night {
                [
                    f'{player.user.username}   {player.is_alive}   {player.status_list}'
                    for player in game.players
                ]
            }"
        )
        logger.info(str(game))
        await self.wakeup_game_loop(game.id)

    async def conduct_day_vote_stage(
        self,
        game_id: str,
        vote_timeout=90,
        second_stage_candidates: list[Player] | None = None,
    ):
        logger.debug(f"conduct_day_vote_stage {game_id}")

        game = await self._game_service.get_game_by_id(game_id)
        logger.debug(
            f"conduct_day_vote_stage: {[f'{player.user.username} {player.is_alive}' for player in game.players]}"
        )
        if second_stage_candidates:
            for player in game.players:
                if player.is_alive and player not in second_stage_candidates:
                    player += PlayerStatusEnum.UNTARGETABLE

        vote_order = await self._get_talk_order(game)
        for i in vote_order:
            player = game.players[i]
            if not player.is_alive or player[PlayerStatusEnum.DISABLED_PREV]:
                continue

            candidate_id = None

            # отправить всем
            vote_event_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.EVENT,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(
                    text=f"Голосует игрок {player.user.username}",
                ),
            )
            await self._websocket_manager.send_broadcast(vote_event_message, game.id)

            # отправить персонально
            action_request_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.ACTION_REQUEST,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameActionRequestPayload(
                    text="Ваша очередь голосовать", timeout=vote_timeout
                ),
            )
            await self._websocket_manager.send_to_one(
                action_request_message, game.id, player.user.id
            )

            # ождидать голос
            event_listener = self._game_event_listeners[game.id]
            try:
                (event_type, target_id) = await asyncio.wait_for(
                    self.wait_for_event(
                        event_listener=event_listener,
                        expected_event=WebSocketGameCommandActionTypeEnum.VOTE,
                    ),
                    timeout=vote_timeout,
                )
                candidate_id = UUID(target_id)
                if event_type == WebSocketGameCommandActionTypeEnum.LEAVE:
                    await self._game_service.leave_game(game.id, player.user.id)

                logger.debug(event_listener)

            # таймаут хода
            except TimeoutError:
                logger.warning(
                    f"Игрок {player.user.username} закончил голосовать (timeout)"
                )
                possible_targets = []
                for candidate in game.players:
                    if (
                        candidate.is_alive
                        and not candidate[PlayerStatusEnum.UNTARGETABLE]
                        and candidate.user.id != player.user.id
                    ):
                        possible_targets.append(candidate)

                random_target = random.choice(possible_targets)
                candidate_id = random_target.user.id
                game = await self._game_service.get_game_by_id(game.id)
                await game.process_vote(player.user.id, random_target.user.id)
                game = await self._game_service.save_game(game)

            except AttributeError:
                continue

            text = ""
            for candidate in game.players:
                if candidate.user.id == candidate_id:
                    text = f"Игрок {player.user.username} проголосовал за {candidate.user.username}"
                    break
            talk_end_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.EVENT,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(text=text),
            )
            await self._websocket_manager.send_broadcast(talk_end_message, game.id)

        game = await self._game_service.get_game_by_id(game.id)
        most_voted = await self._game_service.get_most_voted_players(game)

        most_voted_message = WebSocketMessage(
            message_type=WebSocketMessageTypeEnum.EVENT,
            topic=WebSocketTopicEnum.GAME,
            timestamp=datetime.now().isoformat(),
            payload=WSGameInfoPayload(
                text=f"Кандидаты на выбытие: {', '.join([player.user.username for player in most_voted])}"
            ),
        )
        await self._websocket_manager.send_broadcast(most_voted_message, game.id)

        if len(most_voted) > 1 and not second_stage_candidates:
            await self.announce_new_stage(
                game.id,
                GameStageEnum.DAY_VOTE,
                f"День {game.round_count} Голосование {game.game_stage.value} Второй этап",
            )
            await game.clear_players_votes()
            await self._game_service.save_game(game)
            await self.conduct_day_vote_stage(game.id, vote_timeout, most_voted)

        elif len(most_voted) > 1 and second_stage_candidates:
            no_lynch_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.EVENT,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(
                    text="Город не определился с кандидатом на выбытие"
                ),
            )
            await self._websocket_manager.send_broadcast(no_lynch_message, game.id)
        else:
            lynched_player = await game.resole_voting_stage()
            game = await self._game_service.save_game(game)
            broadcase_lynched_player_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.EVENT,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(
                    text=f"Игрок {lynched_player.user.username} выбыл из игры"
                ),
            )
            await self._websocket_manager.send_broadcast(
                broadcase_lynched_player_message, game.id
            )

            personal_lynched_player_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.EVENT,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameInfoPayload(text="Вы выбыли из игры"),
            )
            await self._websocket_manager.send_to_one(
                personal_lynched_player_message, game.id, lynched_player.user.id
            )

        game = await self._game_service.proceed_next_stage(game)
        logger.info(str(game))
        await self.wakeup_game_loop(game.id)

    async def show_roles(self, game: Game):
        for player in game.players:
            show_role_message = WebSocketMessage(
                message_type=WebSocketMessageTypeEnum.ROLE,
                topic=WebSocketTopicEnum.GAME,
                timestamp=datetime.now().isoformat(),
                payload=WSGameRolePayload(
                    text=f"Вам досталась роль {player.role.role_name}",
                    role=player.role.role_name,
                ),
            )
            await self._websocket_manager.send_to_one(
                show_role_message, game.id, player.user.id
            )

    async def announce_new_stage(
        self, game_id: str, new_stage: GameStageEnum, message: str
    ):
        next_stage_message = WebSocketMessage(
            message_type=WebSocketMessageTypeEnum.NEW_STAGE,
            topic=WebSocketTopicEnum.GAME,
            timestamp=datetime.now().isoformat(),
            payload=WSGameNewStagePayload(new_stage=new_stage, text=message),
        )
        await self._websocket_manager.send_broadcast(next_stage_message, game_id)

    async def _get_talk_order(self, game: Game) -> list[int]:
        logger.debug("_get_talk_order")
        default_talk_order = list(range(len(game.players)))
        talk_order = (
            default_talk_order[int(game.round_count) :]
            + default_talk_order[: int(game.round_count)]
        )
        return talk_order

    async def wait_for_event(
        self,
        event_listener: asyncio.Queue,
        expected_event: WebSocketGameCommandActionTypeEnum,
    ) -> tuple[WebSocketGameCommandActionTypeEnum, str | None]:
        while True:
            event_message: str = await event_listener.get()
            try:
                extra_info = None
                event_parts = event_message.split("|")
                if len(event_parts) == 1:
                    action_type = event_parts[0]
                else:
                    action_type, extra_info = event_parts

                if action_type in (
                    WebSocketGameCommandActionTypeEnum.LEAVE,
                    expected_event,
                ):
                    return (WebSocketGameCommandActionTypeEnum(action_type), extra_info)
                else:
                    continue
            finally:
                event_listener.task_done()

    async def send_game_state(self, game_id: str, user_id: UUID):
        game = await self._game_service.get_game_by_id(game_id)
        is_admin_alive = None
        assigned_role = None
        for player in game.players:
            if player.user.id == game.admin.id:
                is_admin_alive = player.is_alive
            if player.user.id == user_id:
                assigned_role = player.role.role_name

        if assigned_role is None or is_admin_alive is None:
            return

        message = WebSocketMessage(
            message_type=WebSocketMessageTypeEnum.GAME_DATA,
            topic=WebSocketTopicEnum.GAME,
            timestamp=datetime.now().isoformat(),
            payload=WSGameDataPayload(
                id=game.id,
                admin=PlayerResponse(
                    id=game.admin.id,
                    name=game.admin.username,
                    email=game.admin.email,
                    is_alive=is_admin_alive,
                ),
                players=[
                    PlayerResponse(
                        id=player.user.id,
                        name=player.user.username,
                        email=player.user.email,
                        is_alive=player.is_alive,
                    )
                    for player in game.players
                ],
                start_date=game.start_date,
                finish_date=game.finish_date,
                game_stage=game.game_stage,
                game_status=game.game_status,
                round_count=game.round_count,
                winner_team=game.winner_team,
                assigned_role=assigned_role,
            ),
        )
        await self._websocket_manager.send_to_one(message, game_id, user_id)


class RequestScopedProxy:
    """Делегирует вызовы, резолвя сервис в свежем REQUEST-скоупе"""

    def __init__(self, container: AsyncContainer, dependency_type: type):
        self._container = container
        self._type = dependency_type

    def __getattr__(self, name: str):
        async def caller(*args, **kwargs):
            async with self._container() as request_container:
                service = await request_container.get(self._type)
                return await getattr(service, name)(*args, **kwargs)

        return caller
