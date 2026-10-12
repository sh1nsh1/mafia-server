from uuid import UUID

from dishka import FromDishka

from domain.enums import RoleEnum, GameStageEnum, WebSocketTopicEnum
from domain.entities import Game, Lobby, Player
from domain.services import RoleDistributionService
from domain.exceptions import DomainException, RoomNotFoundException
from infrastructure.logger import get_logger
from infrastructure.websocket.dtos import (
    WSGameCommandPayload,
)
from infrastructure.redis.repositories import GameRepository, LobbyRepository


logger = get_logger(f"{__name__}.GameService", 10)


class GameService:
    """
    Сервис для управления единичными операциями над сущностью Game
    """

    def __init__(
        self,
        game_repository: FromDishka[GameRepository],
        lobby_repostory: FromDishka[LobbyRepository],
        role_distribution_service: FromDishka[RoleDistributionService],
    ):
        self._game_repository = game_repository
        self._lobby_reposiroty = lobby_repostory
        self._role_distribution_service = role_distribution_service

    async def create_game_from_lobby(
        self, lobby: Lobby, role_set: list[RoleEnum]
    ) -> Game:
        """
        Создаёт игру из лобби, сохраняет её в лобби и возвращает её
        """
        logger.debug("create_game_from_lobby")
        game = Game(
            id=lobby.id,
            players=await self._role_distribution_service.create_players_with_roles(
                lobby.participants, role_set
            ),
            admin=lobby.admin,
        )

        await self._lobby_reposiroty.prepare_for_game(lobby.id)
        await self._game_repository.create_game(game)
        return game

    async def save_game(self, game: Game) -> Game:
        """
        Сохраняет игру в репозиторий
        """
        logger.info(f"save_game {game.id}")
        return await self._game_repository.save_game(game)

    async def process_role_action(
        self, game_command: WSGameCommandPayload
    ) -> bool | None:
        """
        Обрабатывает ночной ход игрока
        """
        logger.debug(f"process_role_action {game_command.room_id}")
        game = await self.get_game_by_id(game_command.room_id)
        if not game_command.target_id:
            raise DomainException(
                WebSocketTopicEnum.GAME, "WebSocketGameCommand missing target_id"
            )
        result = await game.process_role_action(
            game_command.actor_id, game_command.target_id
        )
        await self.save_game(game)
        return result if isinstance(result, bool) else None

    async def process_vote(self, game_command: WSGameCommandPayload) -> Game:
        """
        Обрабатывает голос игрока
        """
        logger.debug(f"process_vote {game_command.room_id}")
        game = await self.get_game_by_id(game_command.room_id)
        if not game_command.target_id:
            raise DomainException(
                WebSocketTopicEnum.GAME, "WebSocketGameCommand missing target_id"
            )
        await game.process_vote(game_command.actor_id, game_command.target_id)
        return await self.save_game(game)

    async def get_game_by_id(self, game_id: str) -> Game:
        """
        Получает Game из репозитория
        """
        logger.debug(f"get_game_by_id {game_id}")
        game = await self._game_repository.get_game_by_id(game_id)
        if not game:
            raise RoomNotFoundException(context_id=game_id)
        return game

    async def delete_game(self, game_id: str):
        logger.debug(f"delete_game ({game_id})")
        await self._game_repository.delete_game(game_id)

    async def get_night_action_player_groups(
        self, game: Game
    ) -> dict[RoleEnum, list[Player]]:
        action_order: dict[RoleEnum, list[Player]] = {}
        for player in game.players:
            if not player.is_alive:
                continue

            logger.debug(player.role.role_name)
            if not action_order.get(player.role.role_name):
                action_order[player.role.role_name] = [player]
            else:
                action_order[player.role.role_name] += [player]

        action_order.pop(RoleEnum.CITIZEN)
        logger.debug(
            f"get_night_action_player_groups ({game.id}) - {[f'{player.user.username} {player.role.role_name.value}' for player in game.players]}"
        )

        return action_order

    async def get_night_role_action_order(self) -> list[RoleEnum]:
        return [
            RoleEnum.PROSTITUTE,
            RoleEnum.MAFIA_MEMBER,
            RoleEnum.MANIAC,
            RoleEnum.DOCTOR,
            RoleEnum.MAFIA_DON,
            RoleEnum.SHERIFF,
        ]

    async def proceed_next_stage(self, game: Game) -> Game:
        prev_stage = game.game_stage
        game.game_stage = await game.get_next_stage()
        if game.game_stage == GameStageEnum.DAY_TALK:
            game.round_count += 1
            logger.debug(f"round count incremented {game.round_count}")
        logger.debug(
            f"############## proceed_next_stage ({game.id}) from {prev_stage} to {game.game_stage}"
        )
        await self.save_game(game)
        return game

    async def leave_game(self, game_id: str, player_user_id: UUID):
        logger.debug(f"leave_game ({game_id}, {player_user_id}")
        await self._game_repository.remove_player(
            game_id=game_id, player_user_id=str(player_user_id)
        )

    async def get_most_voted_players(self, game: Game) -> list[Player]:
        logger.debug(f"get_most_voted_players ({game.id})")
        most_voted: list[Player] = []
        max_vote_count = 0
        for player in game.players:
            logger.debug(f"watching {player.user.username} votes: {player.votes_count}")
            if not player.is_alive:
                continue
            if int(player.votes_count) > 0:
                if int(player.votes_count) > max_vote_count:
                    most_voted = [player]
                    max_vote_count = int(player.votes_count)
                elif int(player.votes_count) == max_vote_count:
                    most_voted.append(player)
        logger.debug(f"chosen candidates: {most_voted}")
        return most_voted
