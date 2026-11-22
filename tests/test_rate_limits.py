"""Rate limiting on login, register and check-agent (roadmap 1.4)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.rate_limit import FixedWindowRateLimiter, limiter
from app.config import settings
from app.db import get_db
from app.main import create_app

BASE = "/automiteaiapplication/automiteui/auth"
LIMIT = 3
SECRET_PASSWORD = "s3cret-pass-do-not-leak"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", LIMIT)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    limiter.reset()
    app = create_app()
    db = MagicMock()
    db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    limiter.reset()


def login(c):
    return c.post(f"{BASE}/login", json={"username": "nobody", "password": SECRET_PASSWORD})


def register(c):
    # Invalid body (422) still counts: abusive probing must be throttled too.
    return c.post(f"{BASE}/register", json={"username": "x"})


def check(c):
    return c.get(f"{BASE}/check-agent", params={"agent_id": "agent_abc"})


def test_requests_under_limit_are_allowed(client):
    for _ in range(LIMIT):
        assert login(client).status_code == 401


def test_login_limit_exceeded_returns_429_with_retry_after(client):
    for _ in range(LIMIT):
        login(client)
    r = login(client)
    assert r.status_code == 429
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert r.json() == {"detail": "Too many requests. Please try again later."}


@pytest.mark.parametrize("hit", [login, register, check])
def test_each_endpoint_is_limited(client, hit):
    for _ in range(LIMIT):
        assert hit(client).status_code != 429
    assert hit(client).status_code == 429


def test_endpoints_have_independent_counters(client):
    for _ in range(LIMIT):
        login(client)
    assert login(client).status_code == 429
    assert register(client).status_code != 429
    assert check(client).status_code != 429


def test_429_does_not_leak_request_data(client):
    for _ in range(LIMIT):
        login(client)
    r = login(client)
    assert SECRET_PASSWORD not in r.text
    assert "nobody" not in r.text
    assert SECRET_PASSWORD not in str(r.headers)


def test_unrelated_routes_are_not_limited(client):
    for _ in range(LIMIT + 2):
        assert client.get("/automiteaiapplication/health").status_code == 200


def test_window_expiry_with_injected_clock():
    now = [100.0]
    rl = FixedWindowRateLimiter(clock=lambda: now[0])
    assert [rl.hit("k", 2, 60) for _ in range(2)] == [0, 0]
    assert rl.hit("k", 2, 60) == 60
    now[0] += 45
    assert rl.hit("k", 2, 60) == 15
    assert rl.hit("other", 2, 60) == 0  # independent key
    now[0] += 15
    assert rl.hit("k", 2, 60) == 0  # new window
