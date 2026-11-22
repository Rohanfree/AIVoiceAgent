"""Refresh-token rotation/revocation against an in-memory fake Firestore (no live calls)."""
import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from app.auth import refresh_store
from app.auth.jwt_handler import ALGORITHM, create_access_token, create_refresh_token, verify_token
from app.config import settings
from app.routers.auth_router import refresh_token
from app.schemas.auth_models import RefreshRequest


# ─── Fake Firestore ──────────────────────────────────────────────────────────

class FakeSnap:
    def __init__(self, ref, data):
        self.reference = ref
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeRef:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def get(self, transaction=None):
        return FakeSnap(self, self.db.docs.get(self.name))

    def set(self, data):
        self.db.docs[self.name] = dict(data)

    def update(self, data):
        self.db.docs[self.name].update(data)


class FakeQuery:
    def __init__(self, db, field, value):
        self.db, self.field, self.value = db, field, value

    def stream(self):
        return [FakeSnap(FakeRef(self.db, n), d) for n, d in list(self.db.docs.items())
                if d.get(self.field) == self.value]


class FakeCollection:
    def __init__(self, db):
        self.db = db

    def document(self, name):
        return FakeRef(self.db, name)

    def where(self, filter):
        return FakeQuery(self.db, filter.field_path, filter.value)


class FakeTxn:
    def __init__(self):
        self.writes = []

    def update(self, ref, data):
        self.writes.append(("update", ref, data))

    def set(self, ref, data):
        self.writes.append(("set", ref, data))


class FakeDB:
    """Transactions are serialized by a lock, matching Firestore's isolation guarantee."""

    def __init__(self):
        self.docs = {}
        self.lock = threading.Lock()

    def collection(self, name):
        assert name == refresh_store.COLLECTION
        return FakeCollection(self)

    def transaction(self):
        return FakeTxn()


def fake_transactional(fn):
    def run(txn):
        with _CURRENT.lock:
            result = fn(txn)
            for op, ref, data in txn.writes:
                ref.update(data) if op == "update" else ref.set(data)
            return result
    return run


_CURRENT = None


@pytest.fixture
def db(monkeypatch):
    global _CURRENT
    _CURRENT = FakeDB()
    monkeypatch.setattr(refresh_store, "transactional", fake_transactional)
    return _CURRENT


USER = {"sub": "u1", "username": "alice", "client_id": "c1", "is_admin": False}


def _login(db, data=USER):
    return refresh_store.issue_refresh_token(db, dict(data))


def _refresh(db, token):
    return asyncio.run(refresh_token(RefreshRequest(refresh_token=token), db))


def _assert_401(db, token):
    with pytest.raises(HTTPException) as exc:
        _refresh(db, token)
    assert exc.value.status_code == 401


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_issue_stores_record_without_raw_token(db):
    token = _login(db)
    jti = verify_token(token)["jti"]
    rec = db.docs[jti]
    assert rec["used"] is False and rec["revoked"] is False
    assert rec["user_id"] == "u1" and rec["client_id"] == "c1"
    assert rec["expires_at"] > datetime.now(tz=timezone.utc)
    assert token not in repr(db.docs)


def test_valid_rotation_returns_new_pair_and_marks_old_used(db):
    old = _login(db)
    old_jti = verify_token(old)["jti"]
    result = _refresh(db, old)
    assert result.token_type == "bearer" and result.scope == "dashboard"
    assert result.expires_in_minutes == settings.jwt_access_token_expire_minutes
    access = verify_token(result.access_token)
    assert access["scope"] == "dashboard" and access["sub"] == "u1" and access["client_id"] == "c1"
    new = verify_token(result.refresh_token)
    assert new["scope"] == "refresh" and new["jti"] != old_jti
    assert db.docs[old_jti]["used"] is True and db.docs[old_jti]["replaced_by"] == new["jti"]
    assert db.docs[new["jti"]]["family_id"] == db.docs[old_jti]["family_id"]
    # the new token is itself redeemable
    assert _refresh(db, result.refresh_token).refresh_token


def test_admin_rotation_keeps_admin_scope(db):
    tok = _login(db, {"sub": "admin", "username": "root", "is_admin": True})
    assert _refresh(db, tok).scope == "admin:all"


def test_replay_rejected_and_revokes_family(db):
    old = _login(db)
    newer = _refresh(db, old).refresh_token
    _assert_401(db, old)
    # theft response: descendant token is revoked too
    _assert_401(db, newer)
    assert all(r["revoked"] for r in db.docs.values())


def test_tampered_token_rejected(db):
    tok = _login(db)
    head, body, sig = tok.split(".")
    _assert_401(db, f"{head}.{body}.{sig[:-2]}AA")
    _assert_401(db, "not-a-jwt")
    forged = jwt.encode({**verify_token(tok), "sub": "u2"}, "wrong-secret", algorithm=ALGORITHM)
    _assert_401(db, forged)
    assert not any(r["used"] for r in db.docs.values())


def test_expired_token_rejected(db):
    tok = _login(db)
    claims = verify_token(tok)
    expired = jwt.encode({**claims, "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=5)},
                         settings.jwt_secret_key, algorithm=ALGORITHM)
    _assert_401(db, expired)


def test_expired_server_record_rejected(db):
    tok = _login(db)
    db.docs[verify_token(tok)["jti"]]["expires_at"] = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    _assert_401(db, tok)


def test_wrong_scope_rejected(db):
    for scope in ("dashboard", "tool", "admin:all"):
        _assert_401(db, create_access_token({"sub": "u1", "jti": "x"}, scope=scope))
    assert db.docs == {}


def test_missing_jti_or_unknown_jti_rejected(db):
    _assert_401(db, create_refresh_token_without_jti())
    unknown = create_refresh_token(dict(USER), jti="never-stored")
    _assert_401(db, unknown)


def create_refresh_token_without_jti():
    claims = verify_token(create_refresh_token(dict(USER)))
    claims.pop("jti")
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=ALGORITHM)


def test_revoked_record_rejected(db):
    tok = _login(db)
    db.docs[verify_token(tok)["jti"]]["revoked"] = True
    _assert_401(db, tok)


@pytest.mark.parametrize("field,value", [("user_id", "u2"), ("client_id", "c2"), ("is_admin", True)])
def test_user_client_binding_enforced(db, field, value):
    tok = _login(db)
    db.docs[verify_token(tok)["jti"]][field] = value
    _assert_401(db, tok)
    assert len(db.docs) == 1  # no new token minted


def test_token_for_other_client_cannot_use_foreign_record(db):
    a = _login(db)
    jti_a = verify_token(a)["jti"]
    # validly signed token for another client reusing A's jti
    forged = create_refresh_token({**USER, "client_id": "c2"}, jti=jti_a)
    _assert_401(db, forged)
    assert db.docs[jti_a]["used"] is False


def test_missing_database_fails_closed(db):
    tok = _login(db)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(refresh_token(RefreshRequest(refresh_token=tok), None))
    assert exc.value.status_code == 503
    # invalid tokens still 401 without touching the db
    _assert_401(None, "garbage")
    with pytest.raises(refresh_store.RefreshStoreUnavailable):
        refresh_store.issue_refresh_token(None, dict(USER))


def test_database_error_fails_closed(db, monkeypatch):
    tok = _login(db)

    def boom(fn):
        def run(txn):
            raise RuntimeError("firestore down: secret-detail")
        return run

    monkeypatch.setattr(refresh_store, "transactional", boom)
    with pytest.raises(HTTPException) as exc:
        _refresh(db, tok)
    assert exc.value.status_code == 503
    assert "secret-detail" not in str(exc.value.detail)


def test_concurrent_use_only_one_succeeds(db):
    tok = _login(db)
    results = []

    def go():
        try:
            results.append(("ok", _refresh(db, tok)))
        except HTTPException as exc:
            results.append(("err", exc.status_code))

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [r for r, _ in results].count("ok") == 1
    assert all(code == 401 for kind, code in results if kind == "err")


def test_token_values_not_logged(db, caplog):
    caplog.set_level("DEBUG")
    tok = _login(db)
    _refresh(db, tok)
    _assert_401(db, tok)
    assert tok not in caplog.text
