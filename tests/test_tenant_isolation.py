"""Tenant isolation for the four ElevenLabs tool endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.auth.tool_token_store import issue_tool_token
from app.db import get_db
from app.main import create_app
from tests.fake_firestore import FakeDB

BASE = "/automiteaiapplication/elevenlabs-tools"
MOD = "app.routers.agent_tools_elevenlabs"

# route -> valid payload (without client_id)
ROUTES = {
    "get-customer": {"customer_phone": "+15550001"},
    "check-availability": {"service_name": "cut", "date_time": "2030-01-01T10:00:00"},
    "book-appointment": {
        "customer_name": "Sam",
        "customer_phone": "+15550001",
        "service_name": "cut",
        "date_time": "2030-01-01T10:00:00",
    },
    "save-call-summary": {"caller_phone": "+15550001", "summary": "hi"},
}


@pytest.fixture
def client():
    app = create_app()
    fake_db = FakeDB()
    app.dependency_overrides[get_db] = lambda: fake_db
    services = {
        "get_customer_by_phone": MagicMock(return_value=None),
        "get_last_call_summary": MagicMock(return_value=None),
        "check_slot_availability": MagicMock(return_value=(True, None)),
        "create_appointment": MagicMock(return_value=True),
        "create_calendar_event": AsyncMock(),
        "save_call_log": MagicMock(return_value=True),
        "append_call_to_sheet": MagicMock(),
    }
    patchers = [patch(f"{MOD}.{name}", mock) for name, mock in services.items()]
    for p in patchers:
        p.start()
    try:
        _DB[0] = fake_db
        yield TestClient(app), services
    finally:
        for p in patchers:
            p.stop()


_DB = [None]


def _tool_token(client_id="client-a"):
    """A genuinely issued tool token (server-side record in the fake DB)."""
    return issue_tool_token(_DB[0], client_id)[0]


def _post(c, route, token, **extra):
    body = {**ROUTES[route], **extra}
    return c.post(f"{BASE}/{route}", json=body, headers={"Authorization": f"Bearer {token}"})


@pytest.mark.parametrize("route", ROUTES)
def test_tool_token_rejects_other_clients_body_client_id(client, route):
    c, services = client
    resp = _post(c, route, _tool_token("client-a"), client_id="client-b")
    assert resp.status_code == 403
    for mock in services.values():
        mock.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
def test_tool_token_accepts_matching_client_id(client, route):
    c, _ = client
    resp = _post(c, route, _tool_token("client-a"), client_id="client-a")
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("route", ROUTES)
def test_matching_client_id_with_whitespace_still_resolves_to_own_tenant(client, route):
    c, _ = client
    assert _post(c, route, _tool_token("client-a"), client_id=" client-a ").status_code == 200


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_omitted_or_blank_client_id_keeps_400_contract(client, route, value):
    c, services = client
    extra = {} if value is None else {"client_id": value}
    resp = _post(c, route, _tool_token("client-a"), **extra)
    assert resp.status_code == 400
    assert "client_id" in resp.json()["detail"]
    for mock in services.values():
        mock.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("value", [123, ["client-a"], {"id": "client-a"}])
def test_malformed_client_id_is_rejected_without_server_error(client, route, value):
    c, services = client
    resp = _post(c, route, _tool_token("client-a"), client_id=value)
    assert resp.status_code in (400, 403)
    for mock in services.values():
        mock.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
def test_tool_token_without_client_claim_fails_closed(client, route):
    c, services = client
    token = create_access_token({"sub": "client-a"}, scope="tool")
    resp = _post(c, route, token, client_id="client-a")
    assert resp.status_code in (401, 403)
    for mock in services.values():
        mock.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
def test_admin_scope_may_explicitly_act_for_any_client(client, route):
    c, _ = client
    token = create_access_token({"sub": "admin"}, scope="admin:all")
    assert _post(c, route, token, client_id="client-b").status_code == 200


@pytest.mark.parametrize("route", ROUTES)
def test_dashboard_token_remains_rejected(client, route):
    c, services = client
    token = create_access_token({"sub": "u", "client_id": "client-a"}, scope="dashboard")
    resp = _post(c, route, token, client_id="client-a")
    assert resp.status_code == 403
    for mock in services.values():
        mock.assert_not_called()


@pytest.mark.parametrize("route", ROUTES)
def test_missing_token_remains_401(client, route):
    c, _ = client
    resp = c.post(f"{BASE}/{route}", json={**ROUTES[route], "client_id": "client-a"})
    assert resp.status_code == 401


def test_services_receive_the_token_tenant(client):
    c, services = client
    _post(c, "get-customer", _tool_token("client-a"), client_id="client-a")
    assert services["get_customer_by_phone"].call_args.args[1] == "client-a"
