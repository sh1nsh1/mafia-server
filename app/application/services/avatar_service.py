from uuid import UUID

from dishka import FromDishka
from fastapi import UploadFile

from infrastructure.logger_config import get_logger
from infrastructure.database.repositories import AvatarRepository


logger = get_logger(f"{__name__}.AvatarService", 20)


class AvatarService:
    def __init__(
        self,
        avatar_repository: FromDishka[AvatarRepository],
    ):
        self._avatar_repository = avatar_repository

    async def get_user_avatar(self, user_id: UUID) -> bytes | None:
        logger.debug("get_user_avatar")
        return await self._avatar_repository.get_avatar_file(user_id)

    async def set_user_avatar(self, user_id: UUID, file: UploadFile) -> bool:
        logger.debug("set_user_avatar")
        return await self._avatar_repository.upload_avatar(user_id, file)

    async def delete_user_avatar(self, user_id: UUID) -> bool:
        logger.debug("delete_user_avatar")
        return await self._avatar_repository.delete_avatar(user_id)
