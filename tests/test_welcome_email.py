"""Welcome email must never carry the registration password (roadmap 1.5).

Known gap: there is no set-password / password-reset flow yet, so the email contains no
activation link. Users sign in with the password they chose at registration.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.rate_limit import limiter
from app.config import settings
from app.db import get_db
from app.main import create_app

BASE = "/automiteaiapplication/automiteui/auth"
SENTINEL = "SENTINEL-pw-9f3a7c-do-not-leak"


@pytest.fixture
def smtp_enabled(monkeypatch):
    monkeypatch.setattr(settings, "smtp_user", "sender@example.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password-xyz")


@pytest.fixture
def smtp_disabled(monkeypatch):
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_password", "")


@pytest.fixture
def client():
    limiter.reset()
    app = create_app()
    db = MagicMock()
    db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    limiter.reset()


def _payload():
    return {
        "username": "newuser",
        "password": SENTINEL,
        "client_name": "My Salon",
        "elevenlabs_agent_id": "agent_test999",
        "email": "newuser@example.com",
    }


def _register(c):
    with patch(
        "app.services.elevenlabs_service.setup_agent_tools", new_callable=AsyncMock
    ) as setup, patch(
        "app.services.elevenlabs_service.patch_agent_tools", new_callable=AsyncMock
    ), patch(
        "app.services.elevenlabs_service.inject_client_context_into_prompt",
        new_callable=AsyncMock,
    ):
        setup.return_value = ["tool1"]
        return c.post(f"{BASE}/register", json=_payload())


def _app_logs(caplog):
    """Log output from the application's own loggers (excludes the HTTP test client's request dump)."""
    return "\n".join(
        r.getMessage() for r in caplog.records if r.name.startswith("app")
    )


def _sent_text(smtp_cls):
    server = smtp_cls.return_value.__enter__.return_value
    return str(server.sendmail.call_args)


def test_builder_has_no_password_parameter_or_content():
    from app.routers.auth_router import _build_welcome_message

    msg = _build_welcome_message("a@example.com", "My Salon", "newuser")
    raw = msg.as_string()
    body = msg.get_payload()[0].get_payload(decode=True).decode()
    for text in (raw, body, msg["Subject"]):
        assert SENTINEL not in text
    assert "newuser" in body
    assert "<td" in body and ">Password<" not in body


def test_registration_success_sends_email_without_password(client, smtp_enabled):
    c, _ = client
    with patch("app.routers.auth_router.smtplib.SMTP") as smtp:
        r = _register(c)
    assert r.status_code == 201
    server = smtp.return_value.__enter__.return_value
    server.sendmail.assert_called_once()
    assert SENTINEL not in _sent_text(smtp)
    sent = server.sendmail.call_args.args[2]
    from email import message_from_string
    parts = message_from_string(sent).get_payload()
    assert SENTINEL not in parts[0].get_payload(decode=True).decode()
    assert SENTINEL not in str(server.mock_calls)
    assert SENTINEL not in str(smtp.mock_calls)
    assert "newuser@example.com" in _sent_text(smtp)


def test_password_not_persisted_in_plaintext(client, smtp_enabled):
    c, db = client
    with patch("app.routers.auth_router.smtplib.SMTP"):
        _register(c)
    assert SENTINEL not in str(db.mock_calls)


def test_email_disabled_skips_send_and_registration_succeeds(client, smtp_disabled, caplog):
    c, _ = client
    with patch("app.routers.auth_router.smtplib.SMTP") as smtp, caplog.at_level(logging.DEBUG, logger="app"):
        r = _register(c)
    assert r.status_code == 201
    smtp.assert_not_called()
    assert SENTINEL not in _app_logs(caplog)


def test_provider_failure_does_not_break_registration_or_leak(client, smtp_enabled, caplog):
    c, _ = client
    with patch(
        "app.routers.auth_router.smtplib.SMTP",
        side_effect=OSError("connection refused"),
    ) as smtp, caplog.at_level(logging.DEBUG, logger="app"):
        r = _register(c)
    assert r.status_code == 201
    assert "access_token" in r.json()
    assert "Failed to send welcome email" in _app_logs(caplog)
    assert SENTINEL not in _app_logs(caplog)
    assert "OSError" in _app_logs(caplog)
    assert SENTINEL not in r.text
    smtp.assert_called_once()


def test_send_failure_during_sendmail_is_logged_without_password(client, smtp_enabled, caplog):
    import smtplib

    c, _ = client
    with patch("app.routers.auth_router.smtplib.SMTP") as smtp, caplog.at_level(logging.DEBUG, logger="app"):
        smtp.return_value.__enter__.return_value.sendmail.side_effect = smtplib.SMTPException(
            "550 rejected"
        )
        r = _register(c)
    assert r.status_code == 201
    assert SENTINEL not in _app_logs(caplog)
