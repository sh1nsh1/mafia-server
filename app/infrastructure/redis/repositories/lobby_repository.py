import uuid
from uuid import UUID

import redis.asyncio as redis
from dishka import FromDishka

from domain.enums import WebSocketTopicEnum
from domain.exceptions import (
    RepoException,
    LobbyIsFullException,
    RoomNotFoundException,
    UserNotInLobbyException,
    UserAlredyInLobbyException,
    ActionAlreadyPerformedException,
)
from domain.entities.lobby import Lobby
from infrastructure.logger import get_logger
from infrastructure.database.repositories import UserRepository
from infrastructure.redis.models.lobby_model import LobbyModel


logger = get_logger(f"{__name__}.LobbyRepository", 20)


class LobbyRepository:
    def __init__(
        self,
        redis_client: FromDishka[redis.Redis],
        user_repostory: FromDishka[UserRepository],
    ):
        self.redis = redis_client
        self.user_repository = user_repostory
        # Ключ для хэша лобби
        self.LOBBY_KEY = "lobby:{lobby_id}"
        # Ключ для сета lobby: [user]
        self.LOBBY_PARTICIPANTS_KEY = "lobby_participants:{lobby_id}"
        # Ключ для  активных user (тех, что в каких-либо lobby)
        self.ACTIVE_USERS_KEY = "active_users"
        # Время жизни игры
        self.LOBBY_TTL = 1200

    async def create_lobby(self, admin_id: UUID, max_players: int = 10) -> Lobby:
        """
        Создаёт новое лобби

        Args:
            admin_id (int): ID пользователя
            max_players (int): максимальное количество игроков

        Returns:
            Lobby: Доменная сущность Lobby
        """
        logger.debug("create_lobby")
        active_lobby = await self.get_user_active_lobby(admin_id)
        if active_lobby:
            raise UserAlredyInLobbyException(
                context_id=active_lobby.id, user_id=str(admin_id)
            )

        lobby_id = uuid.uuid4().hex[:8]

        lobby_model = LobbyModel(
            id=lobby_id,
            admin_id=admin_id,
            max_players=max_players,
            participant_ids=[admin_id],
        )

        # Используем pipeline для атомарного выполнения
        async with self.redis.pipeline(transaction=True) as pipe:
            # Сохраняем данные лобби и добавляем TTL
            lobby_key = self.LOBBY_KEY.format(lobby_id=lobby_model.id)
            await pipe.hset(
                lobby_key,
                mapping=lobby_model.to_dict(),
            )
            await pipe.expire(lobby_key, self.LOBBY_TTL)

            # Добавляем админа в участники лобби и добавляем TTL
            lobby_participants_key = self.LOBBY_PARTICIPANTS_KEY.format(
                lobby_id=lobby_model.id
            )
            await pipe.sadd(
                lobby_participants_key,
                str(lobby_model.admin_id),
            )
            await pipe.expire(
                lobby_participants_key,
                self.LOBBY_TTL,
            )

            # Добавляем админа в активных пользователей
            # и свзываем с лобби и добавляем TTL
            await pipe.hset(
                self.ACTIVE_USERS_KEY, str(lobby_model.admin_id), lobby_model.id
            )
            await pipe.execute_command(
                "HEXPIRE",
                self.ACTIVE_USERS_KEY,
                self.LOBBY_TTL,
                "FIELDS",
                1,
                str(lobby_model.admin_id),
            )

            # Выполняем все команды
            await pipe.execute()

        return await self._model_to_domain(lobby_model)

    async def get_lobby_by_id(self, lobby_id: str) -> Lobby | None:
        """
        Получает Lobby по его ID, если оно существует, иначе None

        Args:
            lobby_id (str): Lobby ID

        Returns:
            lobby (Lobby | None): Доменная сущность Lobby или None
        """
        logger.debug(f"get_lobby_by_id ({lobby_id})")
        lobby_model = await self._get_lobby_model_by_id(lobby_id)
        logger.debug(lobby_model)
        if not lobby_model:
            return None
        return await self._model_to_domain(lobby_model)

    async def get_all(self):
        """Получение всех лобби"""
        lobby_keys_b = self.redis.scan_iter(match="lobby:*")
        lobbies = []
        async for lobby_key in lobby_keys_b:
            lobby_id = lobby_key.split(":")[1]
            lobbies.append(await self.get_lobby_by_id(lobby_id))

        return lobbies

    async def add_participant(self, lobby_id: str, user_id: UUID) -> Lobby:
        """
        Добавление участника с в Lobby.

        Args:
            lobby_id (str): Lobby ID
            user_id (int): User ID

        Raises:
            UserAlredyInLobbyException: User уже в каком-то лобби
            LobbyNotFoundException: Lobby не сущетсвует
        """
        logger.debug("add_participant")
        # Проверяем, не активен ли пользователь в каком-то лобби
        if active_lobby_id := await self._get_user_active_lobby_id(user_id):
            # уже активен в этом же лобби
            if str(active_lobby_id) == str(lobby_id):
                existing_lobby = await self.get_lobby_by_id(lobby_id)
                if existing_lobby:
                    logger.debug(
                        f"user {user_id} already in lobby {lobby_id} -> reconnect"
                    )
                    return existing_lobby
            raise UserAlredyInLobbyException(
                f"User {user_id} is already active in lobby {active_lobby_id}",
                context_id=lobby_id,
                user_id=str(user_id),
            )

        # Проверяем, есть ли свободное место в лобби
        lobby_model = await self._get_lobby_model_by_id(lobby_id)
        if not lobby_model:
            raise RoomNotFoundException(
                context_id=lobby_id, user_id=str(user_id)
            )  # Данного лобби не сущетсвует

        if (
            not lobby_model
            or len(lobby_model.participant_ids) >= lobby_model.max_players
        ):
            raise LobbyIsFullException(
                context_id=lobby_id, user_id=str(user_id)
            )  # Нет свободного места в лобби

        # Используем WATCH для оптимистичной блокировки
        async with self.redis.pipeline(transaction=True) as pipe:
            try:
                lobby_participants_key = self.LOBBY_PARTICIPANTS_KEY.format(
                    lobby_id=lobby_id
                )
                # Начинаем наблюдение за участниками лобби
                await pipe.watch(lobby_participants_key)

                # Вторая проверка
                if await self._get_user_active_lobby_id(user_id):
                    await pipe.unwatch()
                    raise ActionAlreadyPerformedException(
                        context_id=lobby_id, user_id=str(user_id)
                    )

                # Начинаем транзакцию
                pipe.multi()

                # Добавляем пользователя в список участников лобби
                # и продлеваем TTL
                await pipe.sadd(lobby_participants_key, str(user_id))
                await pipe.expire(
                    self.LOBBY_PARTICIPANTS_KEY.format(lobby_id=lobby_id),
                    self.LOBBY_TTL,
                )

                # Добавляем пользователя в список активных пользователей
                # определяем для него TTL
                await pipe.hset(self.ACTIVE_USERS_KEY, str(user_id), lobby_id)
                await pipe.execute_command(
                    "HEXPIRE",
                    self.ACTIVE_USERS_KEY,
                    self.LOBBY_TTL,
                    "FIELDS",
                    1,
                    str(user_id),
                )

                # Продлеваем TTL лобби
                await pipe.expire(
                    self.LOBBY_KEY.format(lobby_id=lobby_id), self.LOBBY_TTL
                )

                # Выполняем транзакцию
                await pipe.execute()

            except redis.WatchError as e:
                print(e)
                raise RepoException(
                    WebSocketTopicEnum.LOBBY,
                    "Some actions in another sesstion",
                    context_id=lobby_id,
                    user_id=str(user_id),
                )

        new_lobby = await self.get_lobby_by_id(lobby_model.id)
        if not new_lobby:
            raise RoomNotFoundException(
                context_id=lobby_id
            )  # Данного лобби не сущетсвует
        return new_lobby

    async def remove_participant(self, lobby_id: str, user_id: UUID) -> None:
        """
        Удаление User из Lobby.

        Если удаляется админ, Lobby удаляется полностью.

        Args:
            lobby_id (str): Lobby ID
            user_id (int): User ID

        Raises:
            LobbyNotFoundException: Lobby не сущетсвует
        """
        logger.debug("remove_participant")
        lobby_model = await self._get_lobby_model_by_id(lobby_id)
        if not lobby_model:
            logger.warning("RoomNotFoundException")
            raise RoomNotFoundException(context_id=lobby_id)

        active_lobby_id = await self._get_user_active_lobby_id(user_id)
        if not active_lobby_id:
            logger.warning("UserNotInLobbyException")
            raise UserNotInLobbyException(None, lobby_id, str(user_id))

        # Если удаляем админа - удаляем и само лобби
        if str(user_id) == lobby_model.admin_id:
            return await self.delete_lobby(lobby_id)

        async with self.redis.pipeline(transaction=True) as pipe:
            lobby_participants_key = self.LOBBY_PARTICIPANTS_KEY.format(
                lobby_id=lobby_id
            )
            await pipe.watch(lobby_participants_key)
            await pipe.watch(self.ACTIVE_USERS_KEY)

            pipe.multi()
            await pipe.srem(lobby_participants_key, str(user_id))
            await pipe.hdel(self.ACTIVE_USERS_KEY, str(user_id))

            await pipe.execute()

    async def delete_lobby(self, lobby_id: str) -> None:
        """
        Полное удаление лобби.

        Args:
            lobby_id (str): Lobby ID

        Raises:
            LobbyNotFoundException: Lobby не сущетсвует
        """
        logger.debug("delete_lobby")
        lobby_model = await self._get_lobby_model_by_id(lobby_id)

        if not lobby_model:
            logger.warning("RoomNotFoundException")
            raise RoomNotFoundException(context_id=lobby_id)

        active_user_ids = list(
            await self.redis.smembers(
                self.LOBBY_PARTICIPANTS_KEY.format(lobby_id=lobby_model.id)
            )
        )

        await self._delete_lobby_data(lobby_id)
        await self._delete_active_users(active_user_ids)

    async def _delete_lobby_data(
        self,
        lobby_id: str,
    ):
        async with self.redis.pipeline(transaction=True) as pipe:
            # Удаляем данные лобби
            await pipe.delete(self.LOBBY_KEY.format(lobby_id=lobby_id))
            # Удалить данные об участниках лобби
            await pipe.delete(self.LOBBY_PARTICIPANTS_KEY.format(lobby_id=lobby_id))
            await pipe.execute()

    async def prepare_for_game(self, lobby_id: str):
        """
        Удалить данные о лобби, сохранив активных юзеров
        """
        await self._delete_lobby_data(lobby_id)
        pass

    async def update_lobby_max_players(self, lobby_id: str, max_players: int) -> None:
        """
        Обновление максимального количества участников Lobby.

        Args:
            lobby_id (str): Lobby ID
            max_players (int): Максимальное количиство участников

        Raises:
            LobbyNotFoundException: Lobby не сущетсвует
        """
        logger.debug("update_lobby_max_players")
        lobby_model = await self._get_lobby_model_by_id(lobby_id)
        if not lobby_model:
            raise RoomNotFoundException(
                context_id=lobby_id
            )  # Данного лобби не сущетсвует

        # Проверяем, что новое значение не меньше текущего количества игроков
        if max_players < len(lobby_model.participant_ids):
            raise LobbyIsFullException(context_id=lobby_id)

        await self.redis.hset(
            self.LOBBY_KEY.format(lobby_id=lobby_id),
            "max_players",
            str(max_players),
        )

    async def get_user_active_lobby(self, user_id: UUID) -> Lobby | None:
        """
        Внутренний метод: Получает Lobby ID в котором находится User c указанным ID

        Args:
            user_id (int): User ID

        Returns:
            lobby (str / None): Доменная модель Lobby
        """
        logger.debug(f"get_user_active_lobby ({user_id})")
        lobby_id = await self._get_user_active_lobby_id(user_id)
        if lobby_id:
            lobby = await self.get_lobby_by_id(lobby_id)
            logger.debug(f"get_user_active_lobby {lobby}")

            return lobby

    async def _get_user_active_lobby_id(self, user_id: UUID) -> str | None:
        """
        Внутренний метод: Получает Lobby ID в котором находится User c указанным ID

        Args:
            user_id (int): User ID

        Returns:
            lobby_id (str / None): ID модели Lobby
        """
        logger.debug(f"_get_user_active_lobby_id ({user_id})")
        all_active_users = await self.redis.hgetall(self.ACTIVE_USERS_KEY)
        logger.debug(f"all acttive users {all_active_users.items()}")
        lobby_id = await self.redis.hget(self.ACTIVE_USERS_KEY, str(user_id))
        logger.debug(f"_get_user_active_lobby_id {lobby_id}")
        return lobby_id

    async def get_user_active_room_id(self, user_id: UUID) -> str | None:
        logger.debug(f"get_user_active_room_id ({user_id})")
        room_id = await self.redis.hget(self.ACTIVE_USERS_KEY, str(user_id))
        return room_id

    async def _get_lobby_model_by_id(self, lobby_id: str) -> LobbyModel | None:
        """
        Внутренний метод: Получает Lobby по ID

        Args:
            lobby_id (str): Lobby ID
            user_id (int): User ID

        Returns:
            lobby_model (LobbyModel / None): Модель Lobby
        """
        logger.debug(f"_get_lobby_model_by_id ({lobby_id})")
        lobby_data = await self.redis.hgetall(self.LOBBY_KEY.format(lobby_id=lobby_id))
        if not lobby_data:
            logger.warning(lobby_data)
            return None

        lobby_participants_key = self.LOBBY_PARTICIPANTS_KEY.format(
            lobby_id=lobby_data["id"]
        )
        lobby_data["participant_ids"] = list(
            await self.redis.smembers(lobby_participants_key)
        )
        logger.debug(lobby_data.items())

        return LobbyModel.from_redis_data(lobby_data)

    async def _delete_active_users(self, user_ids: list[str]):
        """
        Внутренний метод: Удаляет все User, чей id указан в user_ids
        """
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.hdel(self.ACTIVE_USERS_KEY, *user_ids)
            await pipe.execute()

    async def _model_to_domain(self, lobby_model: LobbyModel) -> Lobby:
        """
        Внутренний метод: Преобразует модель в доменную сущность

        Args:
            lobby_model (LobbyModel): Модель Lobby

        Returns:
            lobby (Lobby): Доменная сущность Lobby
        """
        logger.debug("_model_to_domain")
        participants = []

        for user_id in lobby_model.participant_ids:
            logger.debug(f"_model_to_domain got {user_id}")
            user = await self.user_repository.get_user_by_id(UUID(user_id))
            if user:
                participants.append(user)

        logger.debug([f"{user.id} {user.username}" for user in participants])
        logger.debug(lobby_model.admin_id)
        admin_list = [
            user for user in participants if str(user.id) == lobby_model.admin_id
        ]
        logger.debug([f"{user.id} {user.username}" for user in admin_list])

        return Lobby(
            id=lobby_model.id,
            admin=admin_list[0],
            max_players=int(lobby_model.max_players),
            partipants=participants,
            created_at=lobby_model.created_at,
        )

    async def _domain_to_model(self, lobby: Lobby) -> LobbyModel:
        """
        Внутренний метод: Преобразует доменную сущность в модель

        Args:
            lobby (Lobby): Доменная сущность Lobby

        Returns:
            lobby_model (LobbyModel): Модель Lobby
        """
        logger.debug("_domain_to_model")
        participant_ids = []
        for user in lobby.participants:
            if user.id:
                participant_ids.append(user.id)
        return LobbyModel(
            lobby.id,
            str(lobby.admin.id),
            lobby.max_players,
            participant_ids,
            lobby.created_at,
        )
