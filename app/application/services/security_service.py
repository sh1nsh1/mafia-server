import uuid

from dishka import FromDishka
from pwdlib import PasswordHash

from domain.entities import User
from domain.exceptions import AppException, TokenException, DomainException
from application.queries import UserAuthQuery
from application.commands import UserCreateCommand
from application.services import JWTService
from infrastructure.logger import get_logger
from presentation.api.v1.dtos.requests import CurrentUser
from presentation.api.v1.dtos.responses import TokenPair, UserCreateResponse
from infrastructure.database.repositories import UserRepository


logger = get_logger(f"{__name__}.SecurityService", 20)


class SecurityService:
    def __init__(
        self,
        jwt_service: FromDishka[JWTService],
        user_repository: FromDishka[UserRepository],
    ):
        self._jwt_service = jwt_service
        self._user_repository = user_repository
        self._pwd_context = PasswordHash.recommended()
        self._FAKE_HASH = self._pwd_context.hash("nan1kanopasuwaad0")

    def _verify_password(self, plain_password: str, hashed_password: str):
        logger.debug("_verify_password")
        """
        Verifies if a plain_password matches a hashed_password.
        """
        return self._pwd_context.verify(plain_password, hashed_password)

    def _get_password_hash(self, password: str):
        logger.debug("_get_password_hash")

        """
        Hashes a password
        """
        return self._pwd_context.hash(password)

    async def login(self, user_credentials: UserAuthQuery) -> TokenPair:
        logger.debug("login")

        """
        Authenticate user by his credentials and return a pair of access and refresh tokens
        """

        auth_exc = AppException("Wrong username or password")
        current_user = await self._user_repository.get_user_by_username(
            user_credentials.username
        )

        if not current_user:
            # immitate password check for non-existent user
            self._verify_password(user_credentials.password, self._FAKE_HASH)
            logger.error(auth_exc)
            raise auth_exc

        if not self._verify_password(
            user_credentials.password, current_user.hashed_password
        ):
            logger.error(auth_exc)
            raise auth_exc

        token_pair = await self._create_token_pair(current_user.username)
        logger.debug(token_pair.model_dump())
        return token_pair

    async def register_user(self, user_data: UserCreateCommand):
        logger.debug("register_user")

        hashed_password = self._get_password_hash(user_data.password)
        user_id = uuid.uuid4()

        user = User(user_id, user_data.username, user_data.email, hashed_password)
        updated_user = await self._user_repository.create_user(user)
        token_pair = await self._create_token_pair(updated_user.username)
        return UserCreateResponse(
            status="OK",
            message=f"User {user_data.username} successfully registered",
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
        )

    async def refresh_token(self, refresh_token: str):
        try:
            data = await self._jwt_service.decode_token(refresh_token)
            if data["type"] != "refresh":
                raise TokenException(
                    expected_token="refresh", message="Invalid token type"
                )

            username = data["sub"]
            return await self._create_token_pair(username)
        except DomainException as e:
            exc = TokenException(expected_token="refresh", message=e.message)
            logger.error(exc)
            raise exc

    async def get_current_user(self, access_token: str) -> CurrentUser:
        logger.debug("get_current_user")

        try:
            data = await self._jwt_service.decode_token(access_token)

            if data["type"] != "access":
                raise AppException("Invalid")

            user = await self._user_repository.get_user_by_username(data["sub"])
            if not user:
                raise AppException("Пользователь не найдён")

            return CurrentUser(id=user.id, username=user.username, email=user.email)

        except AppException as e:
            exc = TokenException(expected_token="access", message=e.message)
            logger.error(exc)
            raise exc

    async def _create_token_pair(self, username: str) -> TokenPair:
        logger.debug("_create_token_pair")

        jwt_claims = {
            "sub": str(username),
        }

        access_token = await self._jwt_service.create_access_token(jwt_claims, 1200)
        refresh_token = await self._jwt_service.create_refresh_token(jwt_claims, 30)

        return TokenPair(access_token=access_token, refresh_token=refresh_token)
