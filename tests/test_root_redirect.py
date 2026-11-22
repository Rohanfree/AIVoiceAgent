"""test_root_redirect.py — Bare / must 301-redirect to the landing page.

Pins the fix for staging returning 404 detail Not Found on GET /:
the landing lives at /automiteaiapplication/automiteui/pages/landing,
so / permanently redirects there.
"""

import unittest

from starlette.testclient import TestClient

from app.main import LANDING_PATH, UI_PREFIX, create_app


class TestRootRedirect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(), raise_server_exceptions=False)

    def test_root_301_redirects_to_landing(self):
        resp = self.client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers["location"], LANDING_PATH)

    def test_redirect_target_derives_from_ui_prefix(self):
        self.assertEqual(LANDING_PATH, f"{UI_PREFIX}/pages/landing")


if __name__ == "__main__":
    unittest.main()
