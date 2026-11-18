from uuid import UUID
from collections import defaultdict

from dishka import FromDishka

from domain.enums import RoleEnum, GameStageEnum
from domain.entities import Game, Lobby, Player
from domain.services import RoleDistributionService
from domain.exceptions import DomainException, RoomNotFoundException
from application.commands import GameCommand
from infrastructure.logger_config import get_logger
from infrastructure.redis.repositories import GameRepository, LobbyRepository


logger = get_logger(f"{__name__}.GameService", 10)


class GameService:
    """
    Сервис для управления единичными операциями над сущностью Game
    """

    def __init__(
        self,
        game_repository: FromDishka[GameRepository],
        lobby_repository: FromDishka[LobbyRepository],
        role_distribution_service: FromDishka[RoleDistributionService],
    ):
        self._game_repository = game_repository
        self._lobby_repository = lobby_repository
        self._role_distribution_service = role_distribution_service
        self._night_role_action_order = [
            RoleEnum.PROSTITUTE,
            RoleEnum.MAFIA_MEMBER,
            RoleEnum.MANIAC,
            RoleEnum.DOCTOR,
            RoleEnum.MAFIA_DON,
            RoleEnum.SHERIFF,
        ]

    async def create_game_from_lobby(
        self, lobby: Lobby, role_set: list[RoleEnum]
    ) -> Game:
        """
        Создаёт игру из лобби, сохраняет её в лобби и возвращает её
        """
        logger.debug("create_game_from_lobby")
        players = (
            await self._role_distribution_service.create_players_with_roles(
                lobby.participants, role_set
            )
        )
        game = Game(
            id=lobby.id,
            players=players,
            admin=lobby.admin,
        )

        await self._lobby_repository.prepare_for_game(lobby.id)
        await self._game_repository.create_game(game)
        return game

    async def save_game(self, game: Game) -> Game:
        """
        Сохраняет игру в репозиторий
        """
        logger.info(f"save_game {game.id}")
        return await self._game_repository.save_game(game)

    async def process_role_action(
        self,
        game_command: GameCommand,
    ) -> bool | None:
        """
        Обрабатывает ночной ход игрока
        """
        logger.debug(f"process_role_action {game_command.room_id}")
        game = await self.get_game_by_id(game_command.room_id)
        if not game_command.target_id:
            raise DomainException("WebSocketGameCommand missing target_id")
        result = await game.process_role_action(
            game_command.actor_id, game_command.target_id
        )
        await self.save_game(game)
        return result if isinstance(result, bool) else None

    async def process_vote(self, game_command: GameCommand) -> Game:
        """
        Обрабатывает голос игрока
        """
        logger.debug(f"process_vote {game_command.room_id}")
        game = await self.get_game_by_id(game_command.room_id)
        if not game_command.target_id:
            raise DomainException("WebSocketGameCommand missing target_id")
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
        action_order: dict[RoleEnum, list[Player]] = defaultdict(list)

        alive_players = [p for p in game.players if p.is_alive]

        for player in alive_players:
            action_order[player.role.role_name].append(player)

        action_order.pop(RoleEnum.CITIZEN)

        players_info = [
            f"{p.user.username} {p.role.role_name.value}" for p in game.players
        ]

        logger.debug(
            f"get_night_action_player_groups ({game.id}) - {players_info}"
        )

        return dict(action_order)

    async def proceed_next_stage(self, game: Game) -> Game:
        prev_stage = game.game_stage
        game.game_stage = await game.get_next_stage()

        if game.game_stage == GameStageEnum.DAY_TALK:
            game.round_count += 1
            logger.debug(f"round count incremented {game.round_count}")

        logger.debug(
            f"############## proceed_next_stage ({game.id}) "
            f"from {prev_stage} to {game.game_stage}"
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

        candidates: list[Player] = []

        for player in game.players:
            logger.debug(
                f"watching {player.user.username} votes: {player.votes_count}"
            )
            if player.is_alive and player.votes_count > 0:
                candidates.append(player)

        if candidates:
            max_vote_count = max(p.votes_count for p in candidates)
            most_voted = [
                p for p in candidates if p.votes_count == max_vote_count
            ]
        else:
            most_voted = []

        logger.debug(f"chosen candidates: {most_voted}")
        return most_voted
