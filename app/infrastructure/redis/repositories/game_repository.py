import uuid
from datetime import datetime

from dishka import FromDishka
from redis.asyncio import Redis

from domain.enums import (
    RoleEnum,
    TeamEnum,
    GameStageEnum,
    GameStatusEnum,
    PlayerStatusEnum,
)
from domain.exceptions import (
    RepoException,
)
from domain.entities.game import Game
from domain.entities.player import (
    Role,
    Doctor,
    Player,
    Citizen,
    Sheriff,
    MafiaDon,
    Prostitute,
    MafiaMember,
)
from infrastructure.redis.models import GameModel, PlayerModel
from infrastructure.logger_config import get_logger
from infrastructure.database.repositories import UserRepository


logger = get_logger(f"{__name__}.GameRepository")


class GameRepository:
    def __init__(
        self,
        redis_client: FromDishka[Redis],
        user_repository: FromDishka[UserRepository],
    ):
        self.redis = redis_client
        self._user_repository = user_repository

        # Ключ для хэша лобби
        self.GAME_KEY = "game:{game_id}"
        # Ключ для сета lobby: (user)
        self.GAME_PARTICIPANTS_KEY = "game_participants:{game_id}"
        # Ключ для хранения информации об игроке
        self.PLAYER_KEY = "player:{player_user_id}"
        # Ключ для хранения активных игроков
        self.ACTIVE_USERS_KEY = "active_users"

        self.GAME_TTL = 60 * 60 * 2

    async def get_game_by_id(self, game_id: str) -> Game | None:
        """
        Получить доменную сущность Game
        """
        logger.debug(f"get_game_by_id {game_id}")
        game_model = await self._get_game_model_by_id(game_id)
        return await self._model_to_domain(game_model) if game_model else None

    async def create_game(self, game: Game):
        """
        Создание новой игры
        """
        logger.debug(f"create_game {game.id}")
        logger.debug(game.players)
        player_models = [
            await self._player_to_model(player) for player in game.players
        ]
        game_model = await self._domain_to_model(game)
        logger.debug(game_model.to_dict())
        # Используем pipeline для атомарного выполнения
        async with self.redis.pipeline(transaction=True) as pipe:
            game_key = self.GAME_KEY.format(game_id=game_model.id)
            # Сохраняем данные игры
            await pipe.hset(
                game_key,
                mapping=game_model.to_dict(),
            )

            await pipe.expire(game_key, self.GAME_TTL)

            # Сохраняем данные всех игроков
            for player_model in player_models:
                if player_model:
                    # сохранить данные игрока
                    player_key = self.PLAYER_KEY.format(
                        player_user_id=player_model.user_id
                    )
                    await pipe.hset(
                        player_key,
                        mapping=player_model.to_dict(),
                    )
                    await pipe.expire(player_key, self.GAME_TTL)
                    # связать игрока с игрой
                    game_participants_key = self.GAME_PARTICIPANTS_KEY.format(
                        game_id=game_model.id
                    )
                    await pipe.sadd(
                        game_participants_key,
                        player_model.user_id,
                    )
                    await pipe.expire(game_participants_key, self.GAME_TTL)

                    await pipe.hset(
                        self.ACTIVE_USERS_KEY,
                        str(player_model.user_id),
                        game_model.id,
                    )
                    await pipe.execute_command(
                        "HEXPIRE",
                        self.ACTIVE_USERS_KEY,
                        self.GAME_TTL,
                        "FIELDS",
                        1,
                        str(player_model.user_id),
                    )

            # Выполняем все команды
            await pipe.execute()

    async def save_game(self, game: Game):
        """
        Сохранение Game в Redis
        """
        game_model = await self._domain_to_model(game)
        player_models = [
            await self._player_to_model(player) for player in game.players
        ]
        # Используем pipeline для атомарного выполнения
        async with self.redis.pipeline(transaction=True) as pipe:
            # Сохраняем данные игры
            await pipe.hset(
                self.GAME_KEY.format(game_id=game_model.id),
                mapping=game_model.to_dict(),
            )

            # Сохраняем данные всех игроков
            for player_model in player_models:
                if player_model:
                    # сохранить данные игрока
                    await pipe.hset(
                        self.PLAYER_KEY.format(
                            player_user_id=player_model.user_id
                        ),
                        mapping=player_model.to_dict(),
                    )
                    # связать игрока с игрой
                    await pipe.sadd(
                        self.GAME_PARTICIPANTS_KEY.format(
                            game_id=game_model.id
                        ),
                        player_model.user_id,
                    )

            # Выполняем все команды
            await pipe.execute()

        return game

    async def remove_player(self, game_id: str, player_user_id: str) -> bool:
        """
        Удаление участника из Game.
        Если удаляется админ, Game удаляется полностью.
        """
        logger.debug(f"remove_player {player_user_id} in{game_id}")
        game_model = await self._get_game_model_by_id(game_id)

        if not game_model:
            return False

        # Если удаляем админа - удаляем и само лобби
        if player_user_id == game_model.admin_id:
            return await self.delete_game(game_id)

        async with self.redis.pipeline(transaction=True) as pipe:
            game_participants_key = self.GAME_PARTICIPANTS_KEY.format(
                game_id=game_id
            )

            await pipe.watch(game_participants_key)
            await pipe.watch(self.ACTIVE_USERS_KEY)

            pipe.multi()
            # удалить игрока из списка игроков
            await pipe.srem(game_participants_key, player_user_id)
            # удалить игрока из хэша активных пользователей
            await pipe.hdel(self.ACTIVE_USERS_KEY, player_user_id)
            # удалить данные игрока
            await pipe.delete(
                self.PLAYER_KEY.format(player_user_id=player_user_id)
            )

            await pipe.execute()

        return True

    async def delete_game(self, game_id: str) -> bool:
        """
        Полное удаление Game.
        """
        logger.debug(f"delete_game {game_id}")
        game_model = await self._get_game_model_by_id(game_id)

        if not game_model:
            return False

        game_participants_key = self.GAME_PARTICIPANTS_KEY.format(
            game_id=game_id
        )
        active_user_ids = await self.redis.smembers(game_participants_key)

        async with self.redis.pipeline(transaction=True) as pipe:
            # Удаляем данные игры
            await pipe.delete(self.GAME_KEY.format(game_id=game_id))
            # Удаляем пользователей из списка активных
            await pipe.hdel(self.ACTIVE_USERS_KEY, *active_user_ids)
            # Удаляем список игроков игры
            await pipe.delete(game_participants_key)

            await pipe.execute()

        deleted_active_users = list(active_user_ids)
        check = await self.redis.smismember(
            self.ACTIVE_USERS_KEY, deleted_active_users
        )
        check_status = [
            f"{deleted_active_users[i]} acitve - {bool(check[i])}"
            for i in range(len(active_user_ids))
        ]
        logger.info(f"check if deleted:\n{check_status}")
        return True

    async def get_player_by_user_id(self, player_user_id: str) -> Player:
        logger.debug(f"get_player_by_user_id {player_user_id}")
        user = await self._user_repository.get_user_by_id(
            uuid.UUID(player_user_id)
        )
        if not user:
            raise RepoException(
                message=f"User {player_user_id} not found in DB",
                user_id=player_user_id,
            )

        player_model = await self._get_player_model_by_user_id(player_user_id)
        if not player_model:
            raise RepoException(
                message=f"Player {player_user_id} not found in Redis",
                user_id=player_user_id,
            )
        player_status_list = []
        if player_model.status_list:
            player_status_list = [
                PlayerStatusEnum(status)
                for status in player_model.status_list.split("|")
            ]
        logger.debug(
            f"player_status_list {player_status_list} "
            f"is alive {player_model.is_alive}"
        )
        role = await self._create_role_from_name(player_model.role_name.value)
        if not role:
            exc = RepoException(
                message=f"Role not found {player_model.role_name.value}",
                user_id=player_user_id,
            )
            logger.error(exc)
            raise exc
        return Player(
            user=user,
            role=role,
            status_list=player_status_list,
            is_alive=bool(int(player_model.is_alive)),
            votes_count=int(player_model.votes_count),
        )

    async def _get_game_model_by_id(self, game_id: str) -> GameModel | None:
        """
        Получение Game по ID.
        """
        logger.debug(f"_get_game_model_by_id {game_id}")
        # Получаем данные лобби из Hash
        game_data = await self.redis.hgetall(
            self.GAME_KEY.format(game_id=game_id)
        )

        if not game_data:
            return None

        game_participants_key = self.GAME_PARTICIPANTS_KEY.format(
            game_id=game_data["id"]
        )
        game_data["player_ids"] = list(
            await self.redis.smembers(game_participants_key)
        )

        return GameModel.from_redis_data(game_data)

    async def _save_game_to_db(self, game_id: str, lobby: GameModel):
        """
        Асинхронное сохранение игры в БД (история).
        Вызывается после создания игры.
        """
        # Здесь будет логика сохранения в PostgreSQL/MySQL
        # Например, через asyncpg или SQLAlchemy с asyncio
        pass

    async def _domain_to_model(self, game: Game) -> GameModel:
        """
        Внутренний метод: Преобразует доменную сущность в модель
        Args:
            game (Game): Доменная сущность Game
        Returns:
            game_model (GameModel): Модель Game
        """
        logger.debug(f"_domain_to_model {game.id}")
        game_model = GameModel(
            id=game.id,
            player_ids=[player.user.id for player in game.players],
            admin_id=game.admin.id,
            round_count=game.round_count,
            start_date=game.start_date.isoformat(),
            game_status=game.game_status,
            game_stage=game.game_stage,
            winner_team=game.winner_team or TeamEnum.NONE,
            finish_date=game.finish_date.isoformat()
            if game.finish_date
            else "",
        )
        return game_model

    async def _model_to_domain(self, game_model: GameModel) -> Game:
        logger.debug(f"_model_to_domain {game_model.id}")
        players = [
            await self.get_player_by_user_id(player_user_id)
            for player_user_id in game_model.player_ids
        ]

        admin = await self._user_repository.get_user_by_id(
            uuid.UUID(game_model.admin_id)
        )
        if not admin:
            raise RepoException(
                message=f"Admin not found in game {game_model.id}",
                context_id=game_model.id,
            )
        game = Game(
            id=game_model.id,
            players=players,
            admin=admin,
            start_date=datetime.fromisoformat(game_model.start_date),
            winner_team=TeamEnum(game_model.winner_team),
            game_status=GameStatusEnum(game_model.game_status),
            game_stage=GameStageEnum(game_model.game_stage),
            finish_date=datetime.fromisoformat(game_model.finish_date)
            if game_model.finish_date
            else None,
            round_count=int(game_model.round_count),
        )

        return game

    async def _player_to_model(self, player: Player) -> PlayerModel:
        logger.debug(f"_player_to_model {player.user.username}")
        logger.debug(f"_player_to_model {player.is_alive}")
        player_model = PlayerModel(
            str(player.user.id),
            int(player.is_alive),
            int(player.votes_count),
            player.role.role_name,
            "|".join([status.value for status in player.status_list]),
        )
        logger.debug(player_model)
        return player_model

    async def _get_player_model_by_user_id(
        self, player_user_id: str
    ) -> PlayerModel | None:
        logger.debug(f"_get_player_model_by_user_id {player_user_id}")
        player_data = await self.redis.hgetall(
            self.PLAYER_KEY.format(player_user_id=player_user_id)
        )
        if not player_data:
            return None
        return PlayerModel.from_redis_data(player_data)

    async def _create_role_from_name(self, role_name: str) -> Role | None:
        logger.debug(f"_create_role_from_name ({role_name})")

        match role_name:
            case RoleEnum.CITIZEN.value:
                return Citizen()
            case RoleEnum.MAFIA_MEMBER.value:
                return MafiaMember()
            case RoleEnum.SHERIFF.value:
                return Sheriff()
            case RoleEnum.MAFIA_DON.value:
                return MafiaDon()
            case RoleEnum.PROSTITUTE.value:
                return Prostitute()
            case RoleEnum.DOCTOR.value:
                return Doctor()
