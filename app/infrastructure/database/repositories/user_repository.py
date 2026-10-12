from uuid import UUID

import sqlalchemy.exc as exc
from sqlalchemy import select

from domain.exceptions import RepoException
from domain.entities.user import User
from infrastructure.logger import get_logger
from infrastructure.factories import DBSessionFactory
from infrastructure.database.models.user_model import UserModel


logger = get_logger(f"{__name__}.UserRepository", 20)


class UserRepository:
    def __init__(self, session_factory: DBSessionFactory):
        self.session_factory = session_factory

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """
        Получает User по ID
        Args:
            user_id (int): User ID
        Returns:
            user (User / None): Доменная сущность User или None
        """
        logger.debug("get_user_by_id")
        user_model = await self._get_user_model_by_id(user_id)
        return await self._model_to_domain(user_model) if user_model else None

    async def get_user_by_username(self, username: str) -> User | None:
        """
        Получает User по ID
        Args:
            username (str): имя User
        Returns:
            user (User / None): Доменная сущность User или None
        """
        logger.debug("get_user_by_username")
        user_model = await self._get_user_model_by_username(username)
        return await self._model_to_domain(user_model) if user_model else None

    async def create_user(self, user: User) -> User:
        """
        Получает User по ID
        Args:
            user (User): Доменная сущность User
        Raises
            DatabaseError: Ошибка базы данных
        """
        logger.debug("create_user")
        user_model = await self._domain_to_model(user)
        session = await self.session_factory.get_session()
        async with session:
            async with session.begin():
                try:
                    session.add(user_model)
                    # await session.commit()
                except exc.IntegrityError as e:
                    # await session.rollback()
                    logger.error(e)
                    raise RepoException(*e.args)

                return user

    async def _get_user_model_by_id(self, user_id: UUID) -> UserModel | None:
        logger.debug("_get_user_model_by_id")
        session = await self.session_factory.get_session()
        async with session:
            try:
                statement = select(UserModel).where(UserModel.id == user_id)
                result = await session.execute(statement)
                user_model = result.scalar_one_or_none()
                return user_model
            except exc.IntegrityError as e:
                logger.error(e)
                raise ValueError(e)

    async def _get_user_model_by_username(self, username: str) -> UserModel | None:
        logger.debug("_get_user_model_by_username")
        session = await self.session_factory.get_session()
        async with session:
            try:
                logger.debug("async with session_factory()")
                statement = select(UserModel).where(UserModel.username == username)
                result = await session.execute(statement)
                user_model = result.scalar_one_or_none()
                return user_model
            except exc.IntegrityError as e:
                logger.error(e)
                raise e

    async def _model_to_domain(self, user_model: UserModel) -> User:
        return User(
            username=user_model.username,
            email=user_model.email,
            hashed_password=user_model.hashed_password,
            id=user_model.id,
            created_at=user_model.created_at,
            updated_at=user_model.updated_at,
        )

    async def _domain_to_model(self, user: User) -> UserModel:
        return UserModel(
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            id=user.id,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
