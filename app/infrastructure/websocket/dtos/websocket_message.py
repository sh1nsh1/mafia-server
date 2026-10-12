from domain.enums import WebSocketTopicEnum, WebSocketMessageTypeEnum
from infrastructure.websocket.dtos.ws_game_data_payload import WSGameDataPayload
from infrastructure.websocket.dtos.ws_game_info_payload import WSGameInfoPayload
from infrastructure.websocket.dtos.ws_game_role_payload import WSGameRolePayload
from infrastructure.websocket.dtos.ws_lobby_data_payload import WSLobbyDataPayload
from infrastructure.websocket.dtos.base_websocket_message import BaseWebSocketMessage
from infrastructure.websocket.dtos.ws_game_command_payload import WSGameCommandPayload
from infrastructure.websocket.dtos.ws_lobby_command_payload import WSLobbyCommandPayload
from infrastructure.websocket.dtos.ws_game_new_stage_payload import (
    WSGameNewStagePayload,
)
from infrastructure.websocket.dtos.ws_game_action_request_payload import (
    WSGameActionRequestPayload,
)
from infrastructure.websocket.dtos.ws_user_connection_message_payload import (
    WSUserConnectionMessagePayload,
)


class WebSocketMessage(BaseWebSocketMessage):
    """
    message_type (MessageTypeEnum)
    # topic (MessageTopicEnum)
    timestamp
    payload: {
        "action_type": "role_action" | "vote",
        "actor_role": RoleEnum
        "target": "<player_user_id>"
        "room_id": "<room_id>
    }
    """

    message_type: WebSocketMessageTypeEnum
    topic: WebSocketTopicEnum
    timestamp: str
    payload: (
        WSGameCommandPayload  # COMAND
        | WSGameInfoPayload  # INFO | ERROR
        | WSGameActionRequestPayload  # ACTION_REQUEST
        | WSGameNewStagePayload  # NEW_STAGE
        | WSGameDataPayload  # GAME_DATA
        | WSLobbyDataPayload  # LOBBY_DATA
        | WSLobbyCommandPayload  # COMAND
        | WSUserConnectionMessagePayload  # USER_CONNECT | USER_CONNECT
        | WSGameRolePayload
    )
