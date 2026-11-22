"""Google OAuth tokens are encrypted before Firestore persistence."""
import asyncio
import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings, settings
from app.services import token_crypto as tc
from app.services.calendar_service import create_calendar_event

TOKENS = {
    "token": "ya29.SECRET-ACCESS",
    "refresh_token": "1//SECRET-REFRESH",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "cid.apps.googleusercontent.com",
    "client_secret": "GOCSPX-SECRET-CLIENT",
    "scopes": ["https://www.googleapis.com/auth/calendar"],
}
SECRETS = ["ya29.SECRET-ACCESS", "1//SECRET-REFRESH", "GOCSPX-SECRET-CLIENT"]


def _no_plaintext(payload):
    blob = json.dumps(payload, default=str)
    for s in SECRETS:
        assert s not in blob


def test_round_trip_and_envelope_shape():
    env = tc.encrypt_token_data(TOKENS, "c1")
    assert env["enc_v"] == 1 and set(env) == {"enc_v", "ct"}
    _no_plaintext(env)
    assert tc.decrypt_token_data(env, "c1") == TOKENS


def test_nonce_is_random():
    assert tc.encrypt_token_data(TOKENS, "c1")["ct"] != tc.encrypt_token_data(TOKENS, "c1")["ct"]


def test_tamper_rejected():
    env = tc.encrypt_token_data(TOKENS, "c1")
    raw = bytearray(base64.urlsafe_b64decode(env["ct"]))
    raw[-1] ^= 1
    bad = {**env, "ct": base64.urlsafe_b64encode(bytes(raw)).decode()}
    with pytest.raises(tc.TokenEncryptionError):
        tc.decrypt_token_data(bad, "c1")
    with pytest.raises(tc.TokenEncryptionError):
        tc.decrypt_token_data({**env, "ct": "!!notb64"}, "c1")
    with pytest.raises(tc.TokenEncryptionError):
        tc.decrypt_token_data({**env, "enc_v": 99}, "c1")


def test_wrong_key_rejected(monkeypatch):
    env = tc.encrypt_token_data(TOKENS, "c1")
    monkeypatch.setattr(settings, "secret_key", "a-completely-different-secret-key-value-1234")
    with pytest.raises(tc.TokenEncryptionError):
        tc.decrypt_token_data(env, "c1")


def test_blob_bound_to_client():
    env = tc.encrypt_token_data(TOKENS, "c1")
    with pytest.raises(tc.TokenEncryptionError):
        tc.decrypt_token_data(env, "other-client")


def test_errors_do_not_leak_values():
    env = tc.encrypt_token_data(TOKENS, "c1")
    with pytest.raises(tc.TokenEncryptionError) as exc:
        tc.decrypt_token_data(env, "c2")
    for s in SECRETS + [settings.secret_key]:
        assert s not in str(exc.value)


def test_missing_key_fails_closed_at_runtime(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "")
    with pytest.raises(tc.TokenEncryptionError):
        tc.encrypt_token_data(TOKENS, "c1")
    with pytest.raises(tc.TokenEncryptionError):
        tc.firestore_token_write(TOKENS, "c1")


@pytest.mark.parametrize("key", ["", "   ", "short", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"])
def test_production_startup_requires_strong_secret_key(key):
    base = dict(
        _env_file=None, app_env="production",
        jwt_secret_key="j" * 8 + "Xk29sLq81mZpQw7vN4bRt5yUcE3d",
        admin_password="correct-Horse-battery-9-staple",
    )
    with pytest.raises(ValueError) as exc:
        Settings(secret_key=key, **base)
    assert "SECRET_KEY" in str(exc.value)
    assert key.strip() == "" or key not in str(exc.value)
    Settings(secret_key="k3y-for-token-encryption-0123456789-abcdef", **base)


def test_write_payload_has_no_plaintext_and_replaces_field():
    w = tc.firestore_token_write(TOKENS, "c1")
    _no_plaintext(w["data"])
    assert "google_calendar_tokens" in w["merge"]  # field-path merge replaces legacy map


def _db_with(stored):
    db = MagicMock()
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {"google_calendar_linked": True, "google_calendar_tokens": stored}
    db.collection.return_value.document.return_value.get.return_value = doc
    return db


def _run(db, creds):
    service = MagicMock()
    service.events.return_value.insert.return_value.execute.return_value = {"id": "e", "htmlLink": "l"}
    service.calendars.return_value.get.return_value.execute.return_value = {"timeZone": "UTC"}
    appt = {"date_time": "2026-04-20T14:00:00", "customer_name": "A", "id": "a1"}
    with patch("app.services.calendar_service.get_calendar_service", return_value=(service, creds)):
        return asyncio.run(create_calendar_event(db, "c1", appt))


def _token_sets(db):
    out = []
    for call in db.collection.return_value.document.return_value.set.call_args_list:
        if "google_calendar_tokens" in call.args[0]:
            out.append(call)
    return out


def test_refresh_writes_encrypted_only():
    db = _db_with(tc.encrypt_token_data(TOKENS, "c1"))
    creds = MagicMock(token="ya29.SECRET-REFRESHED")
    assert _run(db, creds) is True
    sets = _token_sets(db)
    assert len(sets) == 1
    blob = json.dumps(sets[0].args[0])
    assert "ya29.SECRET-REFRESHED" not in blob
    _no_plaintext(sets[0].args[0])
    assert tc.decrypt_token_data(sets[0].args[0]["google_calendar_tokens"], "c1")["token"] == "ya29.SECRET-REFRESHED"


def test_legacy_plaintext_read_and_migrated():
    db = _db_with(dict(TOKENS))
    creds = MagicMock(token=TOKENS["token"])  # unchanged -> only migration write
    assert _run(db, creds) is True
    sets = _token_sets(db)
    assert len(sets) == 1
    _no_plaintext(sets[0].args[0])
    assert tc.decrypt_token_data(sets[0].args[0]["google_calendar_tokens"], "c1") == TOKENS


def test_undecryptable_tokens_skip_sync_without_write():
    db = _db_with(tc.encrypt_token_data(TOKENS, "other-client"))
    assert _run(db, MagicMock(token="x")) is False
    assert _token_sets(db) == []


from tests.test_oauth_state import _callback, client, db  # noqa: E402,F401  (fixtures)


def test_oauth_callback_persists_encrypted(client, db, monkeypatch):
    from app.routers import google_auth_router as gar
    db.flow.credentials = MagicMock(token="ya29.SECRET-ACCESS", refresh_token="1//SECRET-REFRESH",
                                    token_uri="u", client_id="c", client_secret="GOCSPX-SECRET-CLIENT",
                                    scopes=["x"])
    _callback(client, gar.create_oauth_state("client-123", None))
    token_writes = [d for _, d in db.sets if "google_calendar_tokens" in d]
    assert len(token_writes) == 1
    _no_plaintext(token_writes[0])
    stored = token_writes[0]["google_calendar_tokens"]
    assert tc.decrypt_token_data(stored, "client-123")["refresh_token"] == "1//SECRET-REFRESH"


def test_oauth_callback_without_key_writes_nothing(client, db, monkeypatch):
    from app.routers import google_auth_router as gar
    monkeypatch.setattr(settings, "secret_key", "")
    resp = _callback(client, gar.create_oauth_state("client-123", None))
    assert "error" in resp.headers["location"]
    assert not [d for _, d in db.sets if "google_calendar_tokens" in d]
