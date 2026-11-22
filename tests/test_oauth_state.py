"""Google OAuth hardening: signed single-use state, return_to allowlist, debug policy."""
import time
import urllib.parse
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import AlreadyExists
from jose import jwt

from app.auth.jwt_handler import create_access_token
from app.config import settings
from app.main import create_app
from app.routers import google_auth_router as gar

BASE = "/automiteaiapplication/client/auth/google"


class FakeDb:
    """Minimal Firestore stand-in: create() is atomic and raises on duplicates."""

    def __init__(self):
        self.docs = {}
        self.sets = []

    def collection(self, name):
        db = self

        class Col:
            def document(self, doc_id):
                key = (name, doc_id)

                class Doc:
                    def create(self, data):
                        if key in db.docs:
                            raise AlreadyExists("exists")
                        db.docs[key] = data

                    def set(self, data, merge=False):
                        db.sets.append((key, data))

                    def get(self):
                        d = MagicMock()
                        d.to_dict.return_value = {"business_name": "Acme", "google_sheet_id": "sheet-1"}
                        return d

                return Doc()

        return Col()


@pytest.fixture
def db():
    fake = FakeDb()
    with patch.object(gar, "get_db", return_value=fake), \
         patch.object(gar, "_send_sheet_notification"), \
         patch.object(gar, "create_client_sheet", return_value="sheet-1"), \
         patch.object(gar, "get_client_config", return_value={"web": {}}), \
         patch.object(gar, "Flow") as flow_cls:
        flow = MagicMock()
        flow.credentials = MagicMock(token="a", refresh_token="r", token_uri="u",
                                     client_id="c", client_secret="s", scopes=["x"])
        flow.authorization_url.side_effect = lambda **kw: (
            "https://accounts.google.com/o/oauth2/auth?state=" + urllib.parse.quote(kw["state"]), kw["state"])
        flow_cls.from_client_config.return_value = flow
        fake.flow = flow
        yield fake


@pytest.fixture
def client():
    return TestClient(create_app(), follow_redirects=False)


def _auth(scope="dashboard", client_id="client-123"):
    data = {"sub": "u"}
    if client_id:
        data["client_id"] = client_id
    return {"Authorization": f"Bearer {create_access_token(data, scope=scope)}"}


def _callback(client, state, **extra):
    params = {"state": state, "code": "auth-code", **extra}
    return client.get(f"{BASE}/callback", params=params)


def _query(resp):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(resp.headers["location"]).query)


# ── state primitives ────────────────────────────────────────────────────────

def test_valid_state_roundtrip():
    claims = gar.verify_oauth_state(gar.create_oauth_state("c1", "/x"))
    assert claims["cid"] == "c1" and claims["r"] == "/x" and claims["jti"]


def _expired_state():
    with patch.object(gar, "OAUTH_STATE_TTL_SECONDS", -5):
        return gar.create_oauth_state("client-123", None)


def test_expired_state_rejected():
    with pytest.raises(ValueError):
        gar.verify_oauth_state(_expired_state())


def test_tampered_state_rejected():
    state = gar.create_oauth_state("c1", None)
    head, body, sig = state.split(".")
    with pytest.raises(ValueError):
        gar.verify_oauth_state(f"{head}.{body}.{sig[:-2]}AA")
    forged = jwt.encode({"typ": "google_oauth_state", "cid": "victim", "jti": "j",
                         "exp": int(time.time()) + 60}, "wrong-key", algorithm="HS256")
    with pytest.raises(ValueError):
        gar.verify_oauth_state(forged)


def test_access_token_is_not_a_valid_state():
    access = create_access_token({"sub": "u", "client_id": "c1"})
    with pytest.raises(ValueError):
        gar.verify_oauth_state(access)


def test_state_does_not_contain_app_jwt():
    access = create_access_token({"sub": "u", "client_id": "c1"})
    assert access not in gar.create_oauth_state("c1", None)


# ── callback behaviour ──────────────────────────────────────────────────────

def test_callback_success_and_replay(client, db):
    state = gar.create_oauth_state("client-123", "/automiteui/pages/dashboard")
    ok = _callback(client, state)
    assert ok.status_code == 307
    assert ok.headers["location"].startswith(settings.base_url.rstrip("/") + "/automiteui/pages/dashboard") \
        or ok.headers["location"].startswith("/automiteui/pages/dashboard")
    assert _query(ok)["google_linked"] == ["success"]
    assert any(k == ("clients", "client-123") for k, _ in db.sets)

    sets_before = len(db.sets)
    replay = _callback(client, state)
    assert _query(replay)["google_linked"] == ["error"]
    assert len(db.sets) == sets_before
    db.flow.fetch_token.assert_called_once()


def test_callback_tampered_state_stores_nothing(client, db):
    state = gar.create_oauth_state("client-123", None)
    resp = _callback(client, state[:-3] + "abc")
    assert _query(resp)["google_linked"] == ["error"]
    assert db.sets == []
    db.flow.fetch_token.assert_not_called()


def test_callback_expired_state(client, db):
    resp = _callback(client, _expired_state())
    assert _query(resp)["google_linked"] == ["error"]
    assert db.sets == []
    db.flow.fetch_token.assert_not_called()


def test_callback_missing_state_redirects_with_error(client, db):
    resp = client.get(f"{BASE}/callback", params={"code": "x"})
    assert resp.status_code == 307
    assert _query(resp)["google_linked"] == ["error"]


def test_callback_provider_error_does_not_exchange_code(client, db):
    state = gar.create_oauth_state("client-123", "/automiteui/pages/dashboard")
    resp = client.get(f"{BASE}/callback", params={"state": state, "error": "access_denied"})
    q = _query(resp)
    assert q["google_linked"] == ["error"] and q["detail"] == ["access_denied"]
    db.flow.fetch_token.assert_not_called()
    assert db.sets == []
    # the state is burned even on provider error
    assert _query(_callback(client, state))["google_linked"] == ["error"]
    db.flow.fetch_token.assert_not_called()


def test_callback_error_detail_does_not_leak_exception_text(client, db):
    db.flow.fetch_token.side_effect = RuntimeError("secret-internal-detail")
    resp = _callback(client, gar.create_oauth_state("client-123", None))
    assert "secret-internal-detail" not in resp.headers["location"]
    assert _query(resp)["google_linked"] == ["error"]


# ── login / start ───────────────────────────────────────────────────────────

def test_start_returns_authorization_url_with_signed_state(client, db):
    resp = client.post(f"{BASE}/start", headers=_auth(), params={"return_to": "/automiteui/pages/dashboard"})
    assert resp.status_code == 200
    url = resp.json()["authorization_url"]
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["state"][0]
    claims = gar.verify_oauth_state(state)
    assert claims["cid"] == "client-123" and claims["r"] == "/automiteui/pages/dashboard"
    assert "Bearer" not in url and _auth()["Authorization"].split()[1] not in url


def test_login_get_requires_header_and_rejects_query_token(client, db):
    token = _auth()["Authorization"].split()[1]
    assert client.get(f"{BASE}/login", params={"token": token}).status_code == 401
    resp = client.get(f"{BASE}/login", headers=_auth())
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://accounts.google.com/")


def test_start_requires_authentication(client, db):
    assert client.post(f"{BASE}/start").status_code == 401


def test_start_missing_client_id_rejected(client, db):
    assert client.post(f"{BASE}/start", headers=_auth(client_id=None)).status_code == 403
    db.flow.authorization_url.assert_not_called()


def test_start_rejects_tool_token(client, db):
    assert client.post(f"{BASE}/start", headers=_auth(scope="tool")).status_code == 403


# ── return_to validation ────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    "https://evil.example/steal",
    "//evil.example/x",
    "/\\evil.example",
    "javascript:alert(1)",
    "https://evil.example@localhost:8090/",
    "http://localhost:8090@evil.example/",
    "https://localhost:8090.evil.example/",
    "/ok\r\nSet-Cookie: a=b",
    "data:text/html,hi",
])
def test_off_list_return_to_rejected(client, db, value):
    resp = client.post(f"{BASE}/start", headers=_auth(), params={"return_to": value})
    assert resp.status_code == 400
    db.flow.authorization_url.assert_not_called()


@pytest.mark.parametrize("value", [
    "/automiteui/pages/dashboard",
    "http://localhost:8090/automiteui/pages/dashboard?x=1",
    "https://auto-mite.com/automiteui/pages/dashboard",
])
def test_allowed_return_to_accepted(client, db, value):
    resp = client.post(f"{BASE}/start", headers=_auth(), params={"return_to": value})
    assert resp.status_code == 200


def test_callback_ignores_off_list_return_to_in_state(client, db):
    # A (hypothetically) signed state carrying an off-list URL must still not redirect off-site.
    state = gar.create_oauth_state("client-123", "https://evil.example/")
    resp = _callback(client, state)
    assert urllib.parse.urlsplit(resp.headers["location"]).netloc != "evil.example"


def test_result_redirect_preserves_existing_query_and_fragment():
    resp = gar._result_redirect("http://localhost:8090/p?a=1#frag", google_linked="success")
    assert resp.headers["location"] == "http://localhost:8090/p?a=1&google_linked=success#frag"


# ── debug endpoint policy ───────────────────────────────────────────────────

def test_debug_requires_auth(client):
    assert client.get(f"{BASE}/debug").status_code == 401


def test_debug_forbidden_for_non_admin(client):
    assert client.get(f"{BASE}/debug", headers=_auth()).status_code == 403


def test_debug_admin_ok_and_no_secrets(client):
    resp = client.get(f"{BASE}/debug", headers=_auth(scope="admin:all"))
    assert resp.status_code == 200
    body = resp.json()
    assert "computed_redirect_uri" in body
    assert settings.jwt_secret_key not in resp.text
