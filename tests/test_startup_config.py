"""Startup validation of JWT/admin secrets (roadmap 1.1)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

STRONG_JWT = "k3Jd9sLq0Zp7VxT2mNb8RcW5yHf1AeUg4oIq6XtS"
STRONG_ADMIN = "correct-Horse-battery-9-staple"
STRONG_SECRET = "k3y-for-token-encryption-0123456789-abcdef"
DEFAULT_JWT = "change-me-to-a-64-char-random-hex-string"
DEFAULT_ADMIN = "Aut0m!te@Secure#2026"


def build(**overrides) -> Settings:
    # _env_file=None keeps a developer's local .env out of the test.
    return Settings(_env_file=None, **overrides)


def prod(**overrides) -> Settings:
    values = {"app_env": "production", "jwt_secret_key": STRONG_JWT, "admin_password": STRONG_ADMIN,
              "secret_key": STRONG_SECRET}
    values.update(overrides)
    return build(**values)


@pytest.mark.parametrize("env", ["development", "Development", "test"])
def test_non_production_accepts_default_secrets(env):
    s = build(app_env=env)
    assert s.jwt_secret_key == DEFAULT_JWT
    assert s.admin_password == DEFAULT_ADMIN


def test_production_accepts_strong_values():
    s = prod()
    assert s.jwt_secret_key == STRONG_JWT


def test_production_is_the_default_environment(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        build()


@pytest.mark.parametrize("env", ["production", "staging", "prod", ""])
def test_anything_but_development_or_test_is_enforced(env):
    with pytest.raises(ValidationError):
        build(app_env=env)


@pytest.mark.parametrize("bad", [DEFAULT_JWT, "", "   ", "short-secret", "a" * 64, "x" * 31])
def test_production_rejects_bad_jwt_secret(bad):
    with pytest.raises(ValidationError) as exc:
        prod(jwt_secret_key=bad)
    assert "JWT_SECRET_KEY" in str(exc.value)


@pytest.mark.parametrize("bad", [DEFAULT_ADMIN, "", "   ", "short1!", "b" * 20])
def test_production_rejects_bad_admin_password(bad):
    with pytest.raises(ValidationError) as exc:
        prod(admin_password=bad)
    assert "ADMIN_PASSWORD" in str(exc.value)


def test_production_rejects_missing_values_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    msg = str(exc.value)
    assert "JWT_SECRET_KEY" in msg and "ADMIN_PASSWORD" in msg


def test_error_never_contains_secret_values():
    weak_jwt, weak_admin = "weak-jwt-sentinel", "weak-admin-sentinel"
    with pytest.raises(ValidationError) as exc:
        prod(jwt_secret_key=weak_jwt, admin_password=weak_admin)
    msg = str(exc.value)
    for secret in (weak_jwt, weak_admin, DEFAULT_JWT, DEFAULT_ADMIN):
        assert secret not in msg
