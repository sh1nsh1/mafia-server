from datetime import datetime

from domain.enums import RoleEnum, TeamEnum, GameStageEnum, GameStatusEnum
from presentation.api.v1.dtos.responses.player_response import PlayerResponse
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage


class WSGameDataPayload(BaseWebSocketMessage):
    id: str
    players: list[PlayerResponse]
    admin: PlayerResponse

    start_date: datetime
    assigned_role: RoleEnum

    winner_team: TeamEnum | None
    game_status: GameStatusEnum
    game_stage: GameStageEnum
    finish_date: datetime | None
    round_count: int
