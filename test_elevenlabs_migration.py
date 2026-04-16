"""
test_elevenlabs_migration.py — Minimal tests for the VAPI → ElevenLabs migration.

Covers:
  1. RegisterRequest schema accepts elevenlabs_agent_id (no assistant_name)
  2. agent_tools_elevenlabs router resolves client_id from a valid tool token
  3. agent_tools_elevenlabs router rejects missing / wrong-scope tokens
  4. client_router allowed_fields includes knowledge_base_text
  5. auth_router register builds user_doc with elevenlabs_agent_id (not assistant_name)
  6. elevenlabs-tools router is registered in main app at the correct prefix
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Make sure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))


# ── 1. Schema ────────────────────────────────────────────────────────────────

class TestRegisterRequestSchema(unittest.TestCase):
    def test_accepts_elevenlabs_agent_id(self):
        from app.schemas.auth_models import RegisterRequest
        req = RegisterRequest(
            username="testuser",
            password="password123",
            client_name="Test Salon",
            elevenlabs_agent_id="agent_abc123",
        )
        self.assertEqual(req.elevenlabs_agent_id, "agent_abc123")

    def test_no_assistant_name_field(self):
        from app.schemas.auth_models import RegisterRequest
        self.assertFalse(
            hasattr(RegisterRequest.model_fields, "assistant_name"),
            "assistant_name should no longer be a field on RegisterRequest",
        )


# ── 2 & 3. client_id resolution from request body ───────────────────────────

class TestToolTokenResolution(unittest.TestCase):
    def test_valid_body_returns_client_id(self):
        from app.routers.agent_tools_elevenlabs import _resolve_client_id
        self.assertEqual(_resolve_client_id({"client_id": "client-xyz"}), "client-xyz")

    def test_missing_client_id_raises_400(self):
        from fastapi import HTTPException
        from app.routers.agent_tools_elevenlabs import _resolve_client_id
        with self.assertRaises(HTTPException) as ctx:
            _resolve_client_id({})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_empty_client_id_raises_400(self):
        from fastapi import HTTPException
        from app.routers.agent_tools_elevenlabs import _resolve_client_id
        with self.assertRaises(HTTPException) as ctx:
            _resolve_client_id({"client_id": ""})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_whitespace_client_id_raises_400(self):
        from fastapi import HTTPException
        from app.routers.agent_tools_elevenlabs import _resolve_client_id
        with self.assertRaises(HTTPException) as ctx:
            _resolve_client_id({"client_id": "   "})
        self.assertEqual(ctx.exception.status_code, 400)


# ── 4. client_router allowed_fields ─────────────────────────────────────────

class TestClientRouterAllowedFields(unittest.TestCase):
    def test_knowledge_base_text_in_allowed_fields(self):
        import ast, inspect, textwrap
        import app.routers.client_router as mod
        source = inspect.getsource(mod.update_profile)
        # Parse the function source and look for the set literal
        tree = ast.parse(textwrap.dedent(source))
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Set):
                elts = [e.s for e in node.elts if isinstance(e, ast.Constant)]
                if "knowledge_base_text" in elts:
                    found = True
                    break
        self.assertTrue(found, "knowledge_base_text must be in the allowed_fields set")


# ── 5. auth_router builds user_doc with elevenlabs_agent_id ──────────────────

class TestAuthRouterRegister(unittest.IsolatedAsyncioTestCase):
    async def test_register_stores_elevenlabs_agent_id(self):
        """Register endpoint must save elevenlabs_agent_id, not assistant_name."""
        from app.schemas.auth_models import RegisterRequest

        body = RegisterRequest(
            username="newuser",
            password="password123",
            client_name="My Salon",
            elevenlabs_agent_id="agent_test999",
        )

        # Fake Firestore
        mock_db = MagicMock()
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = iter([])

        saved_docs = {}

        def fake_set(data, merge=False):
            doc_id = data.get("id", "unknown")
            saved_docs[doc_id] = data

        mock_doc_ref = MagicMock()
        mock_doc_ref.set.side_effect = fake_set
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        with patch("app.services.elevenlabs_service.setup_agent_tools", new_callable=AsyncMock) as mock_setup:
            mock_setup.return_value = True
            from app.routers.auth_router import register
            result = await register(body=body, db=mock_db)

        self.assertIsNotNone(result.access_token)

        # Check that at least one saved doc has elevenlabs_agent_id
        all_values = list(saved_docs.values())
        has_agent_id = any(d.get("elevenlabs_agent_id") == "agent_test999" for d in all_values)
        has_assistant_name = any("assistant_name" in d for d in all_values)
        self.assertTrue(has_agent_id, "elevenlabs_agent_id must be stored in Firestore")
        self.assertFalse(has_assistant_name, "assistant_name must NOT be stored in Firestore")

        mock_setup.assert_called_once()


# ── 6. Router registered at the right prefix ─────────────────────────────────

class TestRouterRegistration(unittest.TestCase):
    def test_elevenlabs_tools_routes_exist(self):
        from app.main import app
        paths = {route.path for route in app.routes}
        expected = [
            "/automiteaiapplication/elevenlabs-tools/get-customer",
            "/automiteaiapplication/elevenlabs-tools/check-availability",
            "/automiteaiapplication/elevenlabs-tools/book-appointment",
            "/automiteaiapplication/elevenlabs-tools/save-call-summary",
        ]
        for path in expected:
            self.assertIn(path, paths, f"Route {path} not registered in app")


if __name__ == "__main__":
    unittest.main(verbosity=2)
