"""
Minimal test: verifies VAPI legacy migration acceptance criteria.

Checks:
  1. VAPI is disabled by default in config
  2. All legacy VAPI files exist in app/legacy/vapi/
  3. No VAPI files remain in app/routers/ or app/services/ or app/schemas/
  4. main.py does not import or register any VAPI router
  5. vapi_service.py functions return early (None/False) when vapi_enabled=False
"""

import importlib
import os
import sys
import types

# ── Point imports to the project root ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))


# ─── 1. Config: vapi_enabled defaults to False ────────────────────────────────

def test_vapi_disabled_by_default():
    from app.config import settings
    assert settings.vapi_enabled is False, "vapi_enabled must default to False"
    assert hasattr(settings, "vapi_api_key"), "vapi_api_key must exist on settings"
    assert hasattr(settings, "vapi_template_assistant_id"), "vapi_template_assistant_id must exist"
    print("PASS  vapi_enabled=False by default")


# ─── 2. Legacy files exist in the right place ─────────────────────────────────

def test_legacy_files_exist():
    expected = [
        "app/legacy/__init__.py",
        "app/legacy/vapi/__init__.py",
        "app/legacy/vapi/agent_tools.py",
        "app/legacy/vapi/vapi_webhook.py",
        "app/legacy/vapi/vapi_service.py",
        "app/legacy/vapi/call_log_service.py",
        "app/legacy/vapi/vapi_models.py",
    ]
    for path in expected:
        assert os.path.exists(path), f"Missing legacy file: {path}"
    print("PASS  all legacy files exist in app/legacy/vapi/")


# ─── 3. VAPI files removed from original locations ───────────────────────────

def test_vapi_files_removed_from_active_locations():
    removed = [
        "app/routers/agent_tools.py",
        "app/routers/vapi_webhook.py",
        "app/services/vapi_service.py",
        "app/services/call_log_service.py",
        "app/schemas/vapi_models.py",
    ]
    for path in removed:
        assert not os.path.exists(path), f"VAPI file still in active location: {path}"
    print("PASS  VAPI files removed from app/routers/, app/services/, app/schemas/")


# ─── 4. main.py does not reference agent_tools or vapi_webhook ───────────────

def test_main_does_not_register_vapi_routers():
    with open("app/main.py") as f:
        source = f.read()
    assert "from app.routers import agent_tools" not in source, \
        "main.py still imports agent_tools from active routers"
    assert "include_router(agent_tools" not in source, \
        "main.py still registers agent_tools router"
    assert "from app.routers import vapi_webhook" not in source, \
        "main.py still imports vapi_webhook"
    print("PASS  main.py does not register any VAPI router")


# ─── 5. vapi_service functions are no-ops when vapi_enabled=False ────────────

import asyncio

def test_vapi_service_noop_when_disabled():
    from app.config import settings
    assert settings.vapi_enabled is False

    # Patch httpx so no real HTTP calls could slip through
    import unittest.mock as mock
    with mock.patch("httpx.AsyncClient") as mock_client:
        from app.legacy.vapi import vapi_service

        result_clone = asyncio.run(
            vapi_service.clone_assistant("Test Biz", "Test Bot")
        )
        result_update = asyncio.run(
            vapi_service.update_assistant("fake-id", {})
        )
        result_toggle = asyncio.run(
            vapi_service.toggle_assistant("fake-id", True)
        )

        mock_client.assert_not_called()  # httpx never instantiated
        assert result_clone is None,  f"clone_assistant should return None, got {result_clone}"
        assert result_update is False, f"update_assistant should return False, got {result_update}"
        assert result_toggle is False, f"toggle_assistant should return False, got {result_toggle}"

    print("PASS  vapi_service functions are no-ops (vapi_enabled=False)")


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_vapi_disabled_by_default,
        test_legacy_files_exist,
        test_vapi_files_removed_from_active_locations,
        test_main_does_not_register_vapi_routers,
        test_vapi_service_noop_when_disabled,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print()
    print(f"{'All tests passed.' if not failed else f'{failed} test(s) failed.'}")
    sys.exit(failed)
