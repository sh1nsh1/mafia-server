import os

import redis
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app, base_url="http://localhost:8000") as c:
        yield c


@pytest.fixture(scope="session")
def redis_client():
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.Redis.from_url(url, decode_responses=True)


@pytest.fixture(scope="session")
def players(client):
    """Логин пяти игроков. Возвращает список {access_token, refresh_token}."""
    result = []
    for i in range(1, 6):
        response = client.post(
            "user/login/",
            data={"username": f"User{i}", "password": f"Userpwd{i}"},
        )
        assert response.status_code == 200, response.text
        result.append(
            {
                "access_token": response.json()["accessToken"],
                "refresh_token": response.cookies["refreshToken"],
            }
        )
    return result


@pytest.fixture(autouse=True)
def _clean_redis(redis_client):
    """Изоляция тестов: лобби/активные игроки живут в Redis (TTL 20 мин),
    поэтому чистим до и после каждого теста."""
    redis_client.flushall()
    yield
    redis_client.flushall()
