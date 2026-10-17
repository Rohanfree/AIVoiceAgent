"""High-value security, authorization, endpoint, and money regression tests."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt


class FakeDoc:
    def __init__(self, data=None, doc_id="doc", exists=None):
        self._data = data
        self.id = doc_id
        self.exists = (data is not None) if exists is None else exists
        self.reference = self

    def to_dict(self):
        return self._data

    def get(self):
        return self

    def set(self, data, merge=False):
        if merge and self._data:
            self._data.update(data)
        else:
            self._data = data
        self.exists = True

    def delete(self):
        self._data = None
        self.exists = False


class FakeQuery:
    def __init__(self, docs):
        self.docs = docs

    def where(self, **kwargs):
        # The test fake deliberately supports Firestore's common equality shape.
        field_filter = kwargs.get("filter")
        field = getattr(field_filter, "field_path", None)
        value = getattr(field_filter, "value", None)
        if field is None and field_filter is not None:
            field = getattr(field_filter, "_field_path", None)
            value = getattr(field_filter, "_value", None)
        if field:
            return FakeQuery([d for d in self.docs if (d.to_dict() or {}).get(field) == value])
        return self

    def limit(self, n):
        return FakeQuery(self.docs[:n])

    def stream(self):
        return iter(self.docs)


class FakeDB:
    def __init__(self, collections=None):
        self.collections = collections or {}

    def collection(self, name):
        docs = self.collections.setdefault(name, [])
        return FakeCollection(docs)


class FakeCollection(FakeQuery):
    def document(self, doc_id):
        for doc in self.docs:
            if doc.id == doc_id:
                return doc
        doc = FakeDoc(None, doc_id, exists=False)
        self.docs.append(doc)
        return doc


def test_passwords_use_argon2_and_wrong_password_fails():
    from app.auth.password import hash_password, verify_password

    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_claims_scopes_and_expiry_are_enforced():
    from app.auth.jwt_handler import create_access_token, create_refresh_token, verify_token

    access = create_access_token({"sub": "u1"}, scope="dashboard")
    payload = verify_token(access)
    assert payload["sub"] == "u1"
    assert payload["scope"] == "dashboard"
    assert payload["iat"] <= payload["exp"]
    refresh = create_refresh_token({"sub": "u1", "client_id": "c1"})
    assert verify_token(refresh)["scope"] == "refresh"
    expired = create_access_token({"sub": "u1"}, expires_delta=timedelta(seconds=-1))
    assert verify_token(expired) is None


def test_auth_dependencies_require_bearer_and_admin_scope():
    import asyncio
    from app.auth.dependencies import get_current_user, require_admin

    with pytest.raises(HTTPException) as no_auth:
        asyncio.run(get_current_user(None))
    assert no_auth.value.status_code == 401
    with pytest.raises(HTTPException) as not_admin:
        asyncio.run(require_admin({"scope": "dashboard"}))
    assert not_admin.value.status_code == 403
    assert asyncio.run(require_admin({"scope": "admin:all"})) == {"scope": "admin:all"}


def test_auth_routes_are_registered_and_refresh_rejects_non_refresh_token():
    from app.main import create_app
    from app.auth.jwt_handler import create_access_token
    from app.routers.auth_router import refresh_token
    from app.schemas.auth_models import RefreshRequest
    from starlette.routing import Route

    app = create_app()
    paths = {(r.path, tuple(sorted(getattr(r, "methods", ())))) for r in app.routes if isinstance(r, Route)}
    assert ("/automiteaiapplication/automiteui/auth/login", ("POST",)) in paths
    assert ("/automiteaiapplication/automiteui/auth/register", ("POST",)) in paths
    assert ("/automiteaiapplication/automiteui/auth/refresh", ("POST",)) in paths
    with pytest.raises(HTTPException) as exc:
        import asyncio
        asyncio.run(refresh_token(RefreshRequest(refresh_token=create_access_token({"sub": "u"}))))
    assert exc.value.status_code == 401


def test_admin_login_returns_admin_scoped_access_and_refresh_tokens():
    import asyncio
    from app.routers.auth_router import login
    from app.schemas.auth_models import LoginRequest

    with patch("app.routers.auth_router._get_admin_hash", return_value="$argon2id$fake"), \
         patch("app.routers.auth_router.verify_password", return_value=True):
        result = asyncio.run(login(LoginRequest(username="automite_admin", password="secret1"), object()))
    from app.auth.jwt_handler import verify_token
    assert result.scope == "admin:all"
    assert verify_token(result.access_token)["scope"] == "admin:all"
    assert verify_token(result.refresh_token)["scope"] == "refresh"


def test_all_active_tool_routes_are_registered_and_require_tool_scope():
    from app.main import create_app

    app = create_app()
    tool_paths = {
        "/automiteaiapplication/elevenlabs-tools/get-customer",
        "/automiteaiapplication/elevenlabs-tools/check-availability",
        "/automiteaiapplication/elevenlabs-tools/book-appointment",
        "/automiteaiapplication/elevenlabs-tools/save-call-summary",
    }
    routes = {r.path: r for r in app.routes if r.path in tool_paths}
    assert set(routes) == tool_paths
    for route in routes.values():
        dependency_names = {getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies}
        assert "_check_scope" in dependency_names


def test_active_route_inventory_has_auth_and_public_surfaces():
    from app.main import create_app

    app = create_app()
    paths = {r.path for r in app.routes}
    expected = {
        "/automiteaiapplication/automiteui/client-portal/profile",
        "/automiteaiapplication/automiteui/client-portal/appointments",
        "/automiteaiapplication/automiteui/client-portal/call-logs",
        "/automiteaiapplication/automiteui/client-portal/token-usage",
        "/automiteaiapplication/automiteui/mngr-sys-access-78/dashboard",
        "/automiteaiapplication/automiteui/mngr-sys-access-78/clients",
        "/automiteaiapplication/automiteui/mngr-sys-access-78/pricing",
        "/automiteaiapplication/automiteui/extraction/upload-file",
        "/automiteaiapplication/automiteui/api/contact",
        "/automiteaiapplication/client/auth/google/login",
        "/automiteaiapplication/health",
        "/robots.txt",
        "/sitemap.xml",
    }
    assert expected <= paths


def test_private_route_groups_have_authorization_dependencies():
    from app.main import create_app

    app = create_app()
    private_prefixes = (
        "/automiteaiapplication/automiteui/client-portal/",
        "/automiteaiapplication/automiteui/mngr-sys-access-78/",
        "/automiteaiapplication/elevenlabs-tools/",
        "/automiteaiapplication/automiteui/extraction/",
    )
    private_routes = [r for r in app.routes if r.path.startswith(private_prefixes)]
    assert private_routes
    for route in private_routes:
        names = {getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies}
        assert names & {"get_current_user", "require_admin", "_check_scope"}, route.path


def test_client_profile_and_lists_are_scoped_to_token_client():
    import asyncio
    from app.routers.client_router import get_profile, list_appointments, list_call_logs

    db = FakeDB({
        "clients": [FakeDoc({"business_name": "A"}, "client-a"), FakeDoc({"business_name": "B"}, "client-b")],
        "appointments": [FakeDoc({"client_id": "client-a", "date_time": "2026-01-01"}, "a1"), FakeDoc({"client_id": "client-b"}, "b1")],
        "call_logs": [FakeDoc({"client_id": "client-a", "created_at": "2026-01-01"}, "l1"), FakeDoc({"client_id": "client-b"}, "l2")],
    })
    user = {"sub": "u-a", "client_id": "client-a", "scope": "dashboard"}
    assert asyncio.run(get_profile(user, db))["business_name"] == "A"
    assert asyncio.run(list_appointments(user, db))["total"] == 1
    assert asyncio.run(list_call_logs(user, db))["total"] == 1


@pytest.mark.asyncio
async def test_each_tool_validates_input_before_service_calls():
    from app.routers import agent_tools_elevenlabs as tools

    db = FakeDB()
    with pytest.raises(HTTPException) as missing_client:
        await tools.get_customer({}, db)
    assert missing_client.value.status_code == 400
    with pytest.raises(HTTPException) as missing_phone:
        await tools.get_customer({"client_id": "c1"}, db)
    assert missing_phone.value.status_code == 400
    with pytest.raises(HTTPException) as bad_time:
        await tools.check_availability({"client_id": "c1", "service_name": "cut", "date_time": "bad"}, db)
    assert bad_time.value.status_code == 400


@pytest.mark.asyncio
async def test_client_usage_cost_is_rounded_to_six_decimal_places():
    from app.routers.client_router import get_token_usage

    db = FakeDB({"clients": [FakeDoc({"elevenlabs_agent_id": "agent", "price_per_character": 0.000001}, "c1")]})
    with patch("app.services.elevenlabs_service.get_agent_usage", new=AsyncMock(return_value={"total_characters": 3, "conversation_count": 1, "total_duration_secs": 2, "conversations": []})):
        result = await get_token_usage("2026-01-01", "2026-01-01", False, {"client_id": "c1"}, db)
    assert result["estimated_cost"] == 0.000003


@pytest.mark.asyncio
async def test_admin_usage_cost_uses_same_money_rounding():
    from app.routers.admin_router import get_token_usage

    db = FakeDB({"clients": [FakeDoc({"elevenlabs_agent_id": "agent", "price_per_character": 0.000001}, "c1")]})
    with patch("app.services.elevenlabs_service.get_agent_usage", new=AsyncMock(return_value={"total_characters": 3, "conversation_count": 1, "total_duration_secs": 2, "conversations": []})):
        result = await get_token_usage("c1", "2026-01-01", "2026-01-01", {"scope": "admin:all"}, db)
    assert result["estimated_cost"] == 0.000003


def test_active_route_inventory_checks_every_registered_endpoint_method():
    from app.main import create_app

    app = create_app()
    routes = {(route.path, method) for route in app.routes for method in (getattr(route, "methods", None) or ())}
    expected = {
        ("/automiteaiapplication/health", "GET"),
        ("/automiteaiapplication/automiteui/auth/login", "POST"),
        ("/automiteaiapplication/automiteui/auth/check-agent", "GET"),
        ("/automiteaiapplication/automiteui/auth/register", "POST"),
        ("/automiteaiapplication/automiteui/auth/refresh", "POST"),
        ("/automiteaiapplication/automiteui/client-portal/profile", "GET"),
        ("/automiteaiapplication/automiteui/client-portal/profile", "PUT"),
        ("/automiteaiapplication/automiteui/client-portal/change-password", "POST"),
        ("/automiteaiapplication/automiteui/client-portal/appointments", "GET"),
        ("/automiteaiapplication/automiteui/client-portal/call-logs", "GET"),
        ("/automiteaiapplication/automiteui/client-portal/parse-text", "POST"),
        ("/automiteaiapplication/automiteui/client-portal/token-usage", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/dashboard", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{client_id}/status", "PATCH"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{client_id}/subscription", "PATCH"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients", "POST"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{client_id}", "DELETE"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/refresh-tool-tokens", "POST"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/token-usage/{client_id}", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/pricing", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/pricing", "PUT"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{client_id}/pricing", "PATCH"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/elevenlabs/agents", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/elevenlabs/agents/{agent_id}", "GET"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/elevenlabs/agents/duplicate", "POST"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{client_id}/character-limit", "PATCH"),
        ("/automiteaiapplication/automiteui/mngr-sys-access-78/clients/{client_id}/add-characters", "POST"),
        ("/automiteaiapplication/elevenlabs-tools/get-customer", "POST"),
        ("/automiteaiapplication/elevenlabs-tools/check-availability", "POST"),
        ("/automiteaiapplication/elevenlabs-tools/book-appointment", "POST"),
        ("/automiteaiapplication/elevenlabs-tools/save-call-summary", "POST"),
        ("/automiteaiapplication/automiteui/api/contact", "POST"),
        ("/automiteaiapplication/client/auth/google/debug", "GET"),
        ("/automiteaiapplication/client/auth/google/login", "GET"),
        ("/automiteaiapplication/client/auth/google/callback", "GET"),
        ("/automiteaiapplication/automiteui/extraction/parse-text", "POST"),
        ("/automiteaiapplication/automiteui/extraction/upload-file", "POST"),
        ("/automiteaiapplication/automiteui/extraction/confirm", "POST"),
        ("/", "GET"), ("/robots.txt", "GET"), ("/sitemap.xml", "GET"),
        ("/sitemap-pages.xml", "GET"), ("/llms.txt", "GET"),
    }
    assert expected <= routes
    assert not any(path.startswith("/vapi") for path, _ in routes)

