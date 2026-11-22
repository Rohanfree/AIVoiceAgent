"""Tool-token issue/rotation/revocation against a fake Firestore (no live calls)."""
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.auth import tool_token_store as store
from app.auth.jwt_handler import ALGORITHM, create_access_token
from app.config import settings
from app.db import get_db
from app.main import create_app
from tests.fake_firestore import FakeDB

TOOLS = "/automiteaiapplication/elevenlabs-tools"
ADMIN = "/automiteaiapplication/automiteui/mngr-sys-access-78"
MOD = "app.routers.agent_tools_elevenlabs"


@pytest.fixture
def db():
    return FakeDB()


@pytest.fixture
def http(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    patchers = [
        patch(f"{MOD}.get_customer_by_phone", MagicMock(return_value=None)),
        patch(f"{MOD}.get_last_call_summary", MagicMock(return_value=None)),
    ]
    for p in patchers:
        p.start()
    try:
        yield TestClient(app)
    finally:
        for p in patchers:
            p.stop()


def _call(http, token, client_id="c1"):
    return http.post(
        f"{TOOLS}/get-customer",
        json={"client_id": client_id, "customer_phone": "+15550001"},
        headers={"Authorization": f"Bearer {token}"},
    )


def _admin_headers():
    return {"Authorization": "Bearer " + create_access_token({"sub": "admin"}, scope="admin:all")}


def _add_client(db, cid, active=True):
    db.collection("clients").document(cid).set({"id": cid, "is_active": active})


# ─── issue + active use ─────────────────────────────────────────────────────

def test_issue_creates_bound_record_without_raw_token(db):
    token, jti = store.issue_tool_token(db, "c1")
    rec = db.data[store.COLLECTION][jti]
    assert rec["client_id"] == "c1" and rec["revoked"] is False
    assert rec["expires_at"] > datetime.now(tz=timezone.utc)
    assert token not in repr(db.data)
    claims = jwt.get_unverified_claims(token)
    assert claims["jti"] == jti and claims["client_id"] == "c1" and claims["scope"] == "tool"


def test_active_token_authenticates_with_existing_bearer_contract(http, db):
    token, _ = store.issue_tool_token(db, "c1")
    assert _call(http, token).status_code == 200


# ─── rotation / revocation ──────────────────────────────────────────────────

def test_rotation_invalidates_old_token_and_new_works(http, db):
    old, old_jti = store.issue_tool_token(db, "c1")
    new, new_jti = store.rotate_tool_token(db, "c1")
    assert _call(http, old).status_code == 401
    assert _call(http, new).status_code == 200
    assert db.data[store.COLLECTION][old_jti]["revoked"] is True
    assert db.data[store.COLLECTION][old_jti]["replaced_by"] == new_jti
    assert db.data[store.COLLECTION][new_jti]["revoked"] is False
    active = [jti for jti, record in db.data[store.COLLECTION].items() if record["client_id"] == "c1" and not record["revoked"]]
    assert active == [new_jti]


def test_rotation_does_not_touch_other_clients(http, db):
    other, _ = store.issue_tool_token(db, "c2")
    store.issue_tool_token(db, "c1")
    store.rotate_tool_token(db, "c1")
    assert _call(http, other, "c2").status_code == 200


def test_rotation_rolls_back_new_token_when_revocation_fails(db):
    _, old_jti = store.issue_tool_token(db, "c1")

    with patch.object(store, "revoke_client_tool_tokens", side_effect=store.ToolTokenStoreUnavailable("boom")):
        with pytest.raises(store.ToolTokenStoreUnavailable):
            store.rotate_tool_token(db, "c1")

    active = [jti for jti, record in db.data[store.COLLECTION].items() if not record["revoked"]]
    assert active == [old_jti]


def test_explicit_revoke(http, db):
    token, _ = store.issue_tool_token(db, "c1")
    assert store.revoke_client_tool_tokens(db, "c1") == 1
    assert _call(http, token).status_code == 401
    assert store.revoke_client_tool_tokens(db, "c1") == 0


# ─── unknown / tampered / expired ───────────────────────────────────────────

def test_validly_signed_token_without_record_is_rejected(http, db):
    legacy = create_access_token({"sub": "c1", "client_id": "c1"}, scope="tool")
    forged = create_access_token({"sub": "c1", "client_id": "c1", "jti": "nope"}, scope="tool")
    assert _call(http, legacy).status_code == 401
    assert _call(http, forged).status_code == 401


def test_tampered_token_is_rejected(http, db):
    token, _ = store.issue_tool_token(db, "c1")
    head, body, sig = token.split(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    assert _call(http, f"{head}.{body}.{flipped}").status_code == 401
    assert _call(http, "garbage").status_code == 401


def test_wrong_secret_token_is_rejected(http, db):
    _, jti = store.issue_tool_token(db, "c1")
    forged = jwt.encode(
        {"sub": "c1", "client_id": "c1", "jti": jti, "scope": "tool",
         "exp": datetime.now(tz=timezone.utc) + timedelta(days=1)},
        "some-other-secret", algorithm=ALGORITHM,
    )
    assert _call(http, forged).status_code == 401


def test_expired_jwt_is_rejected(http, db):
    token = create_access_token(
        {"sub": "c1", "client_id": "c1", "jti": "j1"}, scope="tool", expires_delta=timedelta(seconds=-5)
    )
    assert _call(http, token).status_code == 401


def test_expired_record_is_rejected_even_if_jwt_is_valid(http, db):
    token, jti = store.issue_tool_token(db, "c1")
    db.data[store.COLLECTION][jti]["expires_at"] = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    assert _call(http, token).status_code == 401


# ─── client binding ─────────────────────────────────────────────────────────

def test_record_bound_to_other_client_is_rejected(http, db):
    token, jti = store.issue_tool_token(db, "c1")
    db.data[store.COLLECTION][jti]["client_id"] = "c2"
    assert _call(http, token).status_code == 401


def test_token_cannot_act_for_another_client(http, db):
    token, _ = store.issue_tool_token(db, "c1")
    assert _call(http, token, client_id="c2").status_code == 403


def test_non_tool_scopes_still_rejected(http, db):
    token = create_access_token({"sub": "u", "client_id": "c1"}, scope="dashboard")
    assert _call(http, token).status_code == 403


def test_admin_scope_still_bypasses_tool_record(http, db):
    token = create_access_token({"sub": "admin"}, scope="admin:all")
    assert _call(http, token, client_id="c9").status_code == 200


def test_store_failure_fails_closed_with_503(http, db):
    token, _ = store.issue_tool_token(db, "c1")
    with patch.object(db, "collection", side_effect=RuntimeError("boom")):
        assert _call(http, token).status_code == 503


def test_manual_client_creation_issues_and_persists_tool_token(http, db):
    response = http.post(
        f"{ADMIN}/clients",
        headers=_admin_headers(),
        json={"username": "vip-user", "password": "Str0ng!Passw0rd", "client_name": "VIP Co"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    client = db.data["clients"][body["client_id"]]
    token_id = client["tool_token_id"]
    assert token_id in db.data[store.COLLECTION]
    assert db.data[store.COLLECTION][token_id]["client_id"] == body["client_id"]
    assert "tool_token" not in body


# ─── admin routes ───────────────────────────────────────────────────────────

def test_admin_routes_require_admin(http, db):
    _add_client(db, "c1")
    dash = {"Authorization": "Bearer " + create_access_token({"sub": "u"}, scope="dashboard")}
    for path in ("/refresh-tool-tokens", "/clients/c1/tool-token/rotate", "/clients/c1/tool-token/revoke"):
        assert http.post(ADMIN + path).status_code == 401
        assert http.post(ADMIN + path, headers=dash).status_code == 403


def test_admin_refresh_rotates_active_clients_and_revokes_old(http, db):
    _add_client(db, "c1")
    _add_client(db, "c2")
    _add_client(db, "off", active=False)
    old1, _ = store.issue_tool_token(db, "c1")
    old_off, _ = store.issue_tool_token(db, "off")

    resp = http.post(f"{ADMIN}/refresh-tool-tokens", headers=_admin_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["clients_affected"] == 2 and set(body["tokens"]) == {"c1", "c2"}

    assert _call(http, old1).status_code == 401
    assert _call(http, body["tokens"]["c1"]).status_code == 200
    assert _call(http, body["tokens"]["c2"], "c2").status_code == 200
    assert _call(http, old_off, "off").status_code == 200  # inactive client left alone
    new_jti = jwt.get_unverified_claims(body["tokens"]["c1"])["jti"]
    assert db.data["clients"]["c1"]["tool_token_id"] == new_jti


def test_admin_rotate_and_revoke_single_client(http, db):
    _add_client(db, "c1")
    old, _ = store.issue_tool_token(db, "c1")

    rot = http.post(f"{ADMIN}/clients/c1/tool-token/rotate", headers=_admin_headers())
    assert rot.status_code == 200
    new = rot.json()["tool_token"]
    assert _call(http, old).status_code == 401 and _call(http, new).status_code == 200

    rev = http.post(f"{ADMIN}/clients/c1/tool-token/revoke", headers=_admin_headers())
    assert rev.status_code == 200 and rev.json()["tokens_revoked"] == 1
    assert _call(http, new).status_code == 401


def test_admin_single_client_routes_404_for_unknown_client(http, db):
    for action in ("rotate", "revoke"):
        resp = http.post(f"{ADMIN}/clients/ghost/tool-token/{action}", headers=_admin_headers())
        assert resp.status_code == 404
    assert store.COLLECTION not in db.data


def test_deleting_client_revokes_its_tool_tokens(http, db):
    _add_client(db, "c1")
    token, _ = store.issue_tool_token(db, "c1")
    assert http.delete(f"{ADMIN}/clients/c1", headers=_admin_headers()).status_code == 200
    assert _call(http, token).status_code == 401


def test_deleting_client_fails_closed_when_token_revocation_unavailable(http, db):
    _add_client(db, "c1")
    db.collection("users").document("u1").set({"client_id": "c1"})
    db.collection("appointments").document("a1").set({"client_id": "c1"})
    db.collection("call_logs").document("l1").set({"client_id": "c1"})
    db.collection("customers").document("cu1").set({"client_id": "c1"})

    with patch("app.routers.admin_router.revoke_client_tool_tokens", side_effect=store.ToolTokenStoreUnavailable):
        response = http.delete(f"{ADMIN}/clients/c1", headers=_admin_headers())

    assert response.status_code == 503
    assert db.data["clients"]["c1"] == {"id": "c1", "is_active": True}
    assert db.data["users"]["u1"]["client_id"] == "c1"
    assert db.data["appointments"]["a1"]["client_id"] == "c1"
    assert db.data["call_logs"]["l1"]["client_id"] == "c1"
    assert db.data["customers"]["cu1"]["client_id"] == "c1"


# ─── no secret leakage ──────────────────────────────────────────────────────

def test_raw_tokens_never_stored_or_logged(http, db, caplog):
    _add_client(db, "c1")
    with caplog.at_level(logging.DEBUG):
        old, _ = store.issue_tool_token(db, "c1")
        resp = http.post(f"{ADMIN}/refresh-tool-tokens", headers=_admin_headers())
        new = resp.json()["tokens"]["c1"]
        _call(http, old)
        _call(http, new)
        _call(http, "tampered.token.value")
        http.post(f"{ADMIN}/clients/c1/tool-token/revoke", headers=_admin_headers())
    logs = caplog.text
    stored = repr(db.data)
    for secret in (old, new):
        assert secret not in logs
        assert secret not in stored
    assert settings.jwt_secret_key not in logs
    assert "tool_token" not in db.data["clients"]["c1"]


def test_registration_stores_token_id_not_raw_token():
    import app.routers.auth_router as ar
    db = FakeDB()
    with patch("app.services.elevenlabs_service.setup_agent_tools", AsyncMock(return_value=["t"])), \
         patch("app.services.elevenlabs_service.patch_agent_tools", AsyncMock(return_value=True)), \
         patch("app.services.elevenlabs_service.inject_client_context_into_prompt", AsyncMock()), \
         patch("app.services.elevenlabs_service.patch_agent_first_message", AsyncMock()), \
         patch.object(ar, "_send_welcome_email"), \
         patch.object(ar, "_issue_refresh", return_value="r"), \
         patch.object(ar, "_find_user_by_username", return_value=None):
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        resp = TestClient(app).post(
            "/automiteaiapplication/automiteui/auth/register",
            json={"username": "alice1", "password": "Str0ng!Passw0rd", "client_name": "Acme",
                  "elevenlabs_agent_id": "agent_1", "business_info": "info", "email": "a@example.com",
                  "first_message": "", "timezone": "UTC"},
        )
    assert resp.status_code == 201, resp.text
    (client_doc,) = db.data["clients"].values()
    assert "tool_token" not in client_doc
    assert client_doc["tool_token_id"] in db.data[store.COLLECTION]
    assert db.data[store.COLLECTION][client_doc["tool_token_id"]]["client_id"] == client_doc["id"]
