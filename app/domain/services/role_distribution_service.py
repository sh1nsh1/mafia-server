from random import shuffle

from domain.enums import RoleEnum
from domain.exceptions import DomainException
from domain.entities.user import User
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
from infrastructure.logger_config import get_logger


logger = get_logger(f"{__name__}.RoleDistributionService", 30)


class RoleDistributionService:
    def __init__(self):
        pass

    async def create_players_with_roles(
        self, users: list[User], role_set: list[RoleEnum]
    ):
        """
        Получить список Player из списка User, с рапределёнными ролями
        из списка названий ролей
        """
        logger.debug(f"create_players_with_roles ({len(users)}, {role_set}")
        role_names: list[
            RoleEnum
        ] = await self._get_recomended_role_names_by_list(len(users), role_set)
        logger.debug(role_names)

        roles_to_distribute: list[Role] = await self._create_role_list(
            role_names
        )
        logger.debug(roles_to_distribute)
        if len(users) != len(roles_to_distribute):
            exc = DomainException(
                "Количество игроков не соотвествует количеству ролей - "
                f"{len(users)}"
            )
            logger.error(exc)
            raise exc

        shuffle(roles_to_distribute)
        players = [
            Player(user, role, [])
            for user, role in zip(users, roles_to_distribute)
        ]

        return players

    async def _get_recomended_role_names_by_list(
        self, player_count, role_set: list[RoleEnum]
    ) -> list[RoleEnum]:
        logger.debug("get_recomended_roles_by_list")
        players_remaining = player_count
        required_roles = [RoleEnum.MAFIA_MEMBER, RoleEnum.CITIZEN]
        if any([role not in role_set for role in required_roles]):
            exc = DomainException("В списке ролей нет необходимых")
            logger.error(exc)
            raise exc

        if player_count < 5:
            exc = DomainException(
                "Количество игроков не соотвествует количеству ролей - "
                f"{player_count}"
            )
            logger.error(exc)
            raise exc
        mafia_number = int(player_count // 3.1)
        logger.debug(mafia_number)
        # add mafia members
        result_role_list: list[RoleEnum] = [
            RoleEnum.MAFIA_MEMBER
        ] * mafia_number
        logger.debug(result_role_list)
        players_remaining -= mafia_number
        # replace mafia member by don (if needed)
        if RoleEnum.MAFIA_DON in role_set and mafia_number > 2:
            result_role_list.remove(RoleEnum.MAFIA_MEMBER)
            result_role_list.append(RoleEnum.MAFIA_DON)
        # add sheriff (in needed)
        if RoleEnum.SHERIFF in role_set and players_remaining > 3:
            result_role_list.append(RoleEnum.SHERIFF)
            players_remaining -= 1
        if RoleEnum.DOCTOR in role_set and players_remaining > 2:
            result_role_list.append(RoleEnum.DOCTOR)
            players_remaining -= 1
        if RoleEnum.PROSTITUTE in role_set and players_remaining > 1:
            result_role_list.append(RoleEnum.PROSTITUTE)
            players_remaining -= 1

        result_role_list += [RoleEnum.CITIZEN] * players_remaining
        logger.debug(result_role_list)
        return result_role_list

    async def _create_role_list(
        self, role_name_list: list[RoleEnum]
    ) -> list[Role]:
        logger.debug("_create_role_list")

        available_role_names = [role.__name__ for role in Role.__subclasses__()]
        logger.debug(available_role_names)
        if any(
            [
                role_name.value not in available_role_names
                for role_name in role_name_list
            ]
        ):
            raise DomainException("Неизвестная роль в списке")
        roles = [
            await self._create_role_from_name(role_name)
            for role_name in role_name_list
        ]
        logger.debug(roles)
        return roles

    async def _create_role_from_name(self, role_name: str) -> Role:
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
            case _:
                raise DomainException("Неизвестная роль в списке")
