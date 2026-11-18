import sys
import logging

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.logger_config import get_logger


class BaseEnv(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class Redis(BaseEnv):
    """Конфигурация Redis"""

    url: str

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class Postgres(BaseEnv):
    """Конфигурация базы данных PostgreSql"""

    drivername: str = "postgresql+asyncpg"
    user: str
    password: str
    host: str
    port: int
    db: str

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")


class JWT(BaseEnv):
    """Конфигурация JWT"""

    algorithm: str
    secret_key: str

    model_config = SettingsConfigDict(env_prefix="JWT_")


class RustFS(BaseEnv):
    volumes: str
    address: str
    console_address: str
    console_enable: str
    cors_allowed_origins: str
    console_cors_allowed_origins: str
    access_key: str
    secret_key: str
    bucket_name: str

    model_config = SettingsConfigDict(env_prefix="RUSTFS_")


class EnvironmentError(RuntimeError):
    model_name: str
    missing_fields: list[str]

    def __init__(self, model_name: str, missing_fields: list[str]):
        super().__init__()
        self.model_name = model_name
        self.missing_fields = missing_fields


class Environment:
    postgres: Postgres
    redis: Redis
    jwt: JWT
    rustfs: RustFS

    def __init__(self):
        self.postgres = Environment.__load(Postgres)
        self.redis = Environment.__load(Redis)
        self.jwt = Environment.__load(JWT)
        self.rustfs = Environment.__load(RustFS)

    @staticmethod
    def read_or_exit():
        try:
            return Environment()
        except EnvironmentError:
            sys.exit(1)

    @staticmethod
    def __load[T: BaseEnv](model: type[T]) -> T:
        try:
            return model()
        except ValidationError as e:
            model_name = model.__name__
            logger = get_logger(model_name, logging.DEBUG)

            missing_fields = [
                Environment.__get_field_name(err)
                for err in e.errors()
                if err["type"] == "missing"
            ]

            logger.error(f"Нехватает переменных окружения: {missing_fields}")
            raise EnvironmentError(model_name, missing_fields)

    @staticmethod
    def __get_field_name(details: ErrorDetails):
        return ".".join(str(p) for p in details["loc"])


env = Environment.read_or_exit()
