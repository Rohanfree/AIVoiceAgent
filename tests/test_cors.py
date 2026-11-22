"""Explicit CORS origins (roadmap 1.2)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings

STRONG_JWT = "k3Jd9sLq0Zp7VxT2mNb8RcW5yHf1AeUg4oIq6XtS"
STRONG_ADMIN = "correct-Horse-battery-9-staple"
STRONG_SECRET = "k3y-for-token-encryption-0123456789-abcdef"
ALLOWED = "https://app.example.com"
OTHER = "https://evil.example.net"
HEALTH = "/automiteaiapplication/health"


def build(**overrides) -> Settings:
    # _env_file=None keeps a developer's local .env out of the test.
    return Settings(_env_file=None, **overrides)


def prod(**overrides) -> Settings:
    values = {"app_env": "production", "jwt_secret_key": STRONG_JWT, "admin_password": STRONG_ADMIN,
              "secret_key": STRONG_SECRET}
    values.update(overrides)
    return build(**values)


def test_development_default_is_local_only():
    s = build(app_env="development")
    assert s.cors_origins == ["http://localhost:8090", "http://127.0.0.1:8090"]
    assert "*" not in s.cors_origins


def test_environment_variable_comma_separated(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", " https://a.example.com/ ,https://b.example.com,, "
    )
    s = build(app_env="development")
    assert s.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_production_accepts_explicit_origins():
    assert prod(cors_allowed_origins=f"{ALLOWED},https://x.example.com").cors_origins == [
        ALLOWED,
        "https://x.example.com",
    ]


@pytest.mark.parametrize("value", ["*", f"{ALLOWED}, *", "", " , "])
def test_production_rejects_wildcard_or_empty(value):
    with pytest.raises(ValidationError) as exc:
        prod(cors_allowed_origins=value)
    assert "CORS_ALLOWED_ORIGINS" in str(exc.value)


@pytest.fixture
def client(monkeypatch):
    from app.main import create_app
    from app.config import settings

    monkeypatch.setattr(settings, "cors_allowed_origins", ALLOWED)
    return TestClient(create_app())


def test_allowed_origin_gets_cors_headers(client):
    r = client.get(HEALTH, headers={"Origin": ALLOWED})
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert r.headers["access-control-allow-credentials"] == "true"


def test_allowed_origin_preflight(client):
    r = client.options(
        HEALTH,
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert "POST" in r.headers["access-control-allow-methods"]


def test_disallowed_origin_gets_no_allow_origin(client):
    r = client.get(HEALTH, headers={"Origin": OTHER})
    assert "access-control-allow-origin" not in r.headers


def test_disallowed_origin_preflight_rejected(client):
    r = client.options(
        HEALTH,
        headers={"Origin": OTHER, "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers
