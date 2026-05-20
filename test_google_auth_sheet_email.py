"""
Tests for google_auth_router — verifies that:
  1. When no sheet exists: a new sheet is created and a notification email is sent.
  2. When a sheet already exists: the existing sheet is reused and a notification email is sent.
  3. Both cases work on reconnect (same client connecting again).
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call


def _make_credentials_mock():
    creds = MagicMock()
    creds.token = "access-token"
    creds.refresh_token = "refresh-token"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "client-id"
    creds.client_secret = "client-secret"
    creds.scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    return creds


def _make_client_doc(data):
    doc = MagicMock()
    doc.to_dict.return_value = data
    return doc


class TestGoogleCallbackSheetEmail(unittest.IsolatedAsyncioTestCase):

    def _common_patches(self):
        """Return a dict of patch targets that every test needs."""
        return {
            "app.routers.google_auth_router.jwt.decode": MagicMock(
                return_value={"client_id": "client-123"}
            ),
            "app.routers.google_auth_router.get_client_config": MagicMock(
                return_value={"web": {}}
            ),
            "app.routers.google_auth_router.get_db": MagicMock(),
            "app.routers.google_auth_router._send_sheet_notification": MagicMock(),
            "app.routers.google_auth_router.create_client_sheet": MagicMock(
                return_value="new-sheet-id"
            ),
        }

    async def _call_callback(self, db_mock, patches_ctx):
        """Import and call google_callback with a fake request."""
        from app.routers.google_auth_router import google_callback
        from starlette.testclient import TestClient

        request = MagicMock()
        request.url = MagicMock()

        import json
        from jose import jwt
        from app.config import settings
        state_data = json.dumps({"t": jwt.encode({"client_id": "client-123"}, settings.jwt_secret_key, algorithm="HS256")})

        return await google_callback(request=request, code="auth-code", state=state_data)

    async def test_new_sheet_created_and_email_sent(self):
        """When no sheet exists: creates one and sends notification."""
        creds = _make_credentials_mock()

        db = MagicMock()
        db.collection.return_value.document.return_value.get.return_value = _make_client_doc(
            {"business_name": "Acme Corp"}  # no google_sheet_id
        )
        db.collection.return_value.document.return_value.set = MagicMock()

        with patch("app.routers.google_auth_router.get_db", return_value=db), \
             patch("app.routers.google_auth_router._send_sheet_notification") as mock_notify, \
             patch("app.routers.google_auth_router.create_client_sheet", return_value="new-sheet-id") as mock_create, \
             patch("app.routers.google_auth_router.get_client_config", return_value={"web": {}}), \
             patch("app.routers.google_auth_router.Flow") as mock_flow_cls:

            flow_instance = MagicMock()
            flow_instance.credentials = creds
            mock_flow_cls.from_client_config.return_value = flow_instance

            import json
            from jose import jwt as jose_jwt
            from app.config import settings
            state = json.dumps({"t": jose_jwt.encode({"client_id": "client-123"}, settings.jwt_secret_key, algorithm="HS256")})

            from app.routers.google_auth_router import google_callback
            request = MagicMock()
            await google_callback(request=request, code="auth-code", state=state)

        mock_create.assert_called_once_with("client-123", "Acme Corp", unittest.mock.ANY)
        mock_notify.assert_called_once_with(creds, "client-123", "Acme Corp", "new-sheet-id", db)
        print("PASS: new sheet created and notification sent")

    async def test_existing_sheet_reused_and_email_sent(self):
        """When a sheet already exists: reuses it and still sends notification."""
        creds = _make_credentials_mock()

        db = MagicMock()
        db.collection.return_value.document.return_value.get.return_value = _make_client_doc(
            {"business_name": "Old Corp", "google_sheet_id": "existing-sheet-id"}
        )

        with patch("app.routers.google_auth_router.get_db", return_value=db), \
             patch("app.routers.google_auth_router._send_sheet_notification") as mock_notify, \
             patch("app.routers.google_auth_router.create_client_sheet") as mock_create, \
             patch("app.routers.google_auth_router.get_client_config", return_value={"web": {}}), \
             patch("app.routers.google_auth_router.Flow") as mock_flow_cls:

            flow_instance = MagicMock()
            flow_instance.credentials = creds
            mock_flow_cls.from_client_config.return_value = flow_instance

            import json
            from jose import jwt as jose_jwt
            from app.config import settings
            state = json.dumps({"t": jose_jwt.encode({"client_id": "client-123"}, settings.jwt_secret_key, algorithm="HS256")})

            from app.routers.google_auth_router import google_callback
            request = MagicMock()
            await google_callback(request=request, code="auth-code", state=state)

        mock_create.assert_not_called()
        mock_notify.assert_called_once_with(creds, "client-123", "Old Corp", "existing-sheet-id", db)
        print("PASS: existing sheet reused, notification sent without creating a new sheet")

    async def test_reconnect_with_existing_sheet_sends_email(self):
        """Reconnecting the same client again reuses the sheet and sends email."""
        creds = _make_credentials_mock()

        db = MagicMock()
        db.collection.return_value.document.return_value.get.return_value = _make_client_doc(
            {"business_name": "Reconnect Corp", "google_sheet_id": "old-sheet-id"}
        )

        with patch("app.routers.google_auth_router.get_db", return_value=db), \
             patch("app.routers.google_auth_router._send_sheet_notification") as mock_notify, \
             patch("app.routers.google_auth_router.create_client_sheet") as mock_create, \
             patch("app.routers.google_auth_router.get_client_config", return_value={"web": {}}), \
             patch("app.routers.google_auth_router.Flow") as mock_flow_cls:

            flow_instance = MagicMock()
            flow_instance.credentials = creds
            mock_flow_cls.from_client_config.return_value = flow_instance

            import json
            from jose import jwt as jose_jwt
            from app.config import settings
            state = json.dumps({"t": jose_jwt.encode({"client_id": "client-123"}, settings.jwt_secret_key, algorithm="HS256")})

            from app.routers.google_auth_router import google_callback
            request = MagicMock()
            await google_callback(request=request, code="auth-code", state=state)

        mock_create.assert_not_called()
        mock_notify.assert_called_once_with(creds, "client-123", "Reconnect Corp", "old-sheet-id", db)
        print("PASS: reconnect reuses existing sheet and sends email")


if __name__ == "__main__":
    unittest.main(verbosity=2)
