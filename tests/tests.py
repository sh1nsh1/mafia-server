import json
import time
from datetime import datetime
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from domain.enums import (
    WebSocketTopicEnum,
    WebSocketMessageTypeEnum,
    WebSocketLobbyCommandTypeEnum,
)
from infrastructure.websocket.dtos import (
    WebSocketMessage,
    WSLobbyCommandPayload,
)


def test_login(players):
    assert len(players) == 5
    assert all(player["access_token"] for player in players)
    assert all(player["refresh_token"] for player in players)


def test_create_and_join_lobby(client: TestClient, redis_client, players):
    admin_token = players[0]["access_token"]
    response = client.post(
        "lobbies/",
        json={"max_players": 5},
        headers={"authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    lobby_id = response.json()["id"]

    with ExitStack() as stack:
        sessions: list[WebSocketTestSession] = []
        lobby_admin = {}
        for i in range(5):
            session = stack.enter_context(
                client.websocket_connect(
                    f"rooms/{lobby_id}",
                    headers={"authorization": f"Bearer {players[i]['access_token']}"},
                )
            )

            sessions.append(session)
            time.sleep(0.02)
            for existing in sessions:
                message = json.loads(existing.receive_json())
                if not lobby_admin:
                    lobby_admin.update(message["payload"]["user"])
                assert message["messageType"] == WebSocketMessageTypeEnum.USER_CONNECT

        for i in range(len(sessions) - 1, -1, -1):
            sessions[i].send_json(
                WebSocketMessage(
                    message_type=WebSocketMessageTypeEnum.COMMAND,
                    topic=(WebSocketTopicEnum.LOBBY),
                    timestamp=datetime.now().isoformat(),
                    payload=WSLobbyCommandPayload(
                        action_type=WebSocketLobbyCommandTypeEnum.LEAVE,
                        role_set=None,
                        room_id=lobby_id,
                        target_id=None,
                    ),
                ).model_dump(mode="json"),
            )
            # Сервер обрабатывает LEAVE и закрывает соединение. Дожидаемся
            # закрытия, чтобы выходы не выполнялись конкурентно (иначе
            # WATCH-транзакции Redis конфликтуют и падают с WatchError).
            with pytest.raises(WebSocketDisconnect):
                while True:
                    sessions[i].receive_json()

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and redis_client.exists(f"lobby:{lobby_id}"):
            time.sleep(0.1)

        assert not redis_client.exists(f"lobby:{lobby_id}"), (
            "лобби не удалено после выхода всех, включая создателя"
        )
        assert redis_client.hlen("active_users") == 0, "active_users не очищен"
