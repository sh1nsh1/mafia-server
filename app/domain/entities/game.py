from uuid import UUID
from datetime import datetime

from domain.enums import (
    RoleEnum,
    TeamEnum,
    GameStageEnum,
    GameStatusEnum,
    PlayerStatusEnum,
)
from domain.exceptions import DomainException
from domain.entities.user import User
from domain.entities.player import Player
from infrastructure.logger_config import get_logger


logger = get_logger(__name__)


class Game:
    id: str
    players: list[Player]
    admin: User

    start_date: datetime

    winner_team: TeamEnum | None
    game_status: GameStatusEnum
    game_stage: GameStageEnum
    finish_date: datetime | None
    round_count: int

    def __init__(
        self,
        id: str,
        players: list[Player],
        admin: User,
        start_date: datetime | None = None,
        winner_team: TeamEnum | None = None,
        game_status: GameStatusEnum = GameStatusEnum.IN_PROGRESS,
        game_stage: GameStageEnum = GameStageEnum.DAY_INTRO,
        finish_date: datetime | None = None,
        round_count: int = 0,
    ):
        self.id = id
        self.players = players
        self.admin = admin

        self.start_date = start_date or datetime.now()
        self.winner_team = winner_team or TeamEnum.NONE
        self.game_status = game_status
        self.game_stage = game_stage
        self.finish_date = finish_date
        self.round_count = round_count

    def __str__(self) -> str:
        return f"Game {self.id} status: {self.game_status}\n{'=' * 80}\n\t\
            round: {self.round_count}\tstage: {self.game_stage}\n\t\
            players:\n{'\n'.join([str(player) for player in self.players])}"

    async def check_finish_condition(self) -> bool:

        end = False
        player_count = len(
            [player for player in self.players if player.is_alive]
        )
        maniac = await self._is_maniac_alive()
        mafia_number = await self._get_alive_mafia_number()

        if mafia_number == 0 and not maniac:
            self.winner_team = TeamEnum.CITIZEN_TEAM
            end = True
        elif mafia_number >= player_count - mafia_number:
            self.winner_team = TeamEnum.MAFIA_TEAM
            end = True
        elif maniac and player_count == 1:
            self.winner_team = TeamEnum.NEUTRAL
            end = True
        else:
            end = False
        logger.debug(f"{self.id} check_finish_condition - {end}")
        return end

    async def process_role_action(
        self, actor_id: UUID, target_id: UUID
    ) -> bool | None:
        actor = None
        target = None

        for player in self.players:
            if player.user.id == actor_id:
                actor = player
            if player.user.id == target_id:
                target = player
            if actor and target:
                break

        if not (actor and target):
            raise DomainException(
                f"Actor or Target not found in game {self.id}"
            )

        result = actor.perform_role_action(target)
        logger.debug(
            f"{self.id} {actor.user.username} process_role_action "
            f"- result {result}"
        )
        return result if isinstance(result, bool) else None

    async def process_vote(self, actor_id: UUID, target_id: UUID):
        actor = None
        target = None

        for player in self.players:
            if player.user.id == actor_id:
                actor = player
            if player.user.id == target_id:
                target = player
            if actor and target:
                break

        if not (actor and target):
            exc = DomainException(
                f"Actor or Target not found in game {self.id}"
            )
            logger.error(exc)
            raise exc

        actor.set_vote(target)
        logger.debug(
            f"{self.id} process_vote {actor.user.id} "
            f"target {target.user.username}"
        )

    async def resolve_night_stage(self) -> list[Player]:
        died_players = []
        for player in self.players:
            if not player.is_alive:
                continue
            if (
                player.role.role_name == RoleEnum.PROSTITUTE
                and await self._is_player_about_to_die(player)
            ):
                disabled_player = await self._get_disabled_player()
                if (
                    disabled_player
                    and not disabled_player[PlayerStatusEnum.HEALED]
                ):
                    disabled_player.die()  # prostitute's visitor dies
                    died_players.append(disabled_player)
                player.die()  # prostitute dies
                died_players.append(player)

            elif (
                await self._is_player_about_to_die(player)
                and not player[PlayerStatusEnum.DISABLED]
            ):
                player.die()  # player dies
                died_players.append(player)

        # clean up statuses after night
        await self.manage_players_statuses()

        died_usernames = [player.user.username for player in died_players]
        logger.debug(f"{self.id} resolve_night_stage - died {died_usernames}")
        return died_players

    async def resole_voting_stage(
        self, players: list[Player] | None = None
    ) -> Player:
        logger.debug(f"{self.id} resole_voting_stage")
        if not players:
            players = self.players
        index_max = 0
        for i in range(len(players)):
            if players[i].is_alive and int(players[i].votes_count) > int(
                players[index_max].votes_count
            ):
                index_max = i

        players[index_max].die()
        return players[index_max]

    async def get_next_stage(self) -> GameStageEnum:
        """
        Переводит игру на следующую стадию и возвращает эту стадию
        """
        logger.debug(f"{self.id} get_next_stage")
        match self.game_stage:
            case GameStageEnum.DAY_INTRO:
                self.game_stage = GameStageEnum.NIGHT
            case GameStageEnum.NIGHT:
                self.game_stage = GameStageEnum.DAY_TALK
            case GameStageEnum.DAY_TALK:
                self.game_stage = GameStageEnum.DAY_VOTE
            case GameStageEnum.DAY_VOTE:
                await self.clear_players_votes()
                self.game_stage = GameStageEnum.NIGHT

        return self.game_stage

    async def manage_players_statuses(self):
        for player in self.players:
            if not player.is_alive:
                continue

            new_status_list = []
            for status in player.status_list:
                match status:
                    case PlayerStatusEnum.HEALED:
                        new_status_list.append(PlayerStatusEnum.HEALED_PREV)
                    case PlayerStatusEnum.DISABLED:
                        new_status_list.append(PlayerStatusEnum.DISABLED_PREV)
            player.status_list = new_status_list

    async def clear_players_votes(self):
        logger.debug(f"{self.id} clear_players_votes")
        for player in self.players:
            player.votes_count = 0

    async def _get_alive_mafia_number(self) -> int:
        mafia_number = 0
        for player in self.players:
            if player.is_alive and player.role.team == TeamEnum.MAFIA_TEAM:
                mafia_number += 1
        logger.debug(f"{self.id} _get_alive_mafia_number - {mafia_number}")
        return mafia_number

    async def _is_maniac_alive(self) -> bool:
        for player in self.players:
            if player.role.role_name == RoleEnum.MANIAC:
                return True
        return False

    async def _is_player_about_to_die(self, player: Player) -> bool:
        result = False
        if (
            (
                player[PlayerStatusEnum.RAIDED]
                == await self._get_alive_mafia_number()
                or player[PlayerStatusEnum.ASSAULTED]
            )
            and not player[PlayerStatusEnum.HEALED]
            and player.is_alive
        ):
            result = True
        logger.debug(
            f"{self.id} {player.user.username} _is_player_about_to_die "
            f"- {result}"
        )
        return result

    async def _get_disabled_player(self) -> Player | None:
        logger.debug(f"{self.id} _get_disabled_player")
        for player in self.players:
            if player[PlayerStatusEnum.DISABLED]:
                return player
