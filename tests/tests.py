import json
import time
from contextlib import ExitStack

from domain.enums import WebSocketMessageTypeEnum


def test_login(players):
    assert len(players) == 5
    assert all(player["access_token"] for player in players)
    assert all(player["refresh_token"] for player in players)


def test_create_and_join_lobby(client, redis_client, players):
    admin_token = players[0]["access_token"]
    response = client.post(
        "lobbies/",
        json={"max_players": 5},
        headers={"authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    lobby_id = response.json()["id"]

    with ExitStack() as stack:
        sessions = []
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
                assert message["messageType"] == WebSocketMessageTypeEnum.USER_CONNECT

        for i in range(len(sessions) - 1, -1, -1):
            sessions[i].close()
            for j in range(i):
                message = json.loads(sessions[j].receive_json())
                assert message["messageType"] == WebSocketMessageTypeEnum.USER_LEAVE

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and redis_client.exists(f"lobby:{lobby_id}"):
            time.sleep(0.1)

        assert not redis_client.exists(f"lobby:{lobby_id}"), (
            "лобби не удалено после выхода всех, включая создателя"
        )
        assert redis_client.hlen("active_users") == 0, "active_users не очищен"
