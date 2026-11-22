"""robots.txt and llms.txt content (SEO.4)."""

import re

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seo.registry import PAGES, indexable_pages

client = TestClient(app)
BASE = settings.public_site_url.rstrip("/")
APP = "/automiteaiapplication"


def _robots() -> str:
    return client.get("/robots.txt").text


def test_single_user_agent_group():
    lines = _robots().splitlines()
    assert [l for l in lines if l.lower().startswith("user-agent")] == ["User-agent: *"]
    assert "" not in lines[: lines.index("") if "" in lines else 0]


def test_disallows_every_noindex_page():
    robots = _robots()
    for page in PAGES:
        if not page.indexable:
            assert f"Disallow: {page.path}" in robots


def test_disallows_private_docs_and_api_surfaces():
    robots = _robots()
    for path in (
        f"{APP}/docs",
        f"{APP}/redoc",
        f"{APP}/openapi.json",
        f"{APP}/automiteui/auth/",
        f"{APP}/automiteui/client-portal/",
        f"{APP}/automiteui/mngr-sys-access-78/",
        f"{APP}/mngr-sys-access-78/",
        f"{APP}/automiteui/extraction/",
        f"{APP}/automiteui/api/",
        f"{APP}/elevenlabs-tools/",
        f"{APP}/client/auth/",
    ):
        assert f"Disallow: {path}" in robots


def test_no_rule_blocks_an_indexable_page():
    disallows = re.findall(r"^Disallow: (\S+)", _robots(), re.M)
    for page in indexable_pages():
        assert not any(page.path.startswith(d) for d in disallows), page.path


def test_sitemap_line_uses_public_site_url():
    assert f"Sitemap: {BASE}/sitemap.xml" in _robots().splitlines()


def test_llms_lists_indexable_pages_and_blog():
    body = client.get("/llms.txt").text
    for page in indexable_pages():
        assert f"({BASE}{page.path})" in body
    assert f"({BASE}/blogs)" in body
    assert f"({BASE}/blogs/llms.txt)" in body


def test_llms_excludes_noindex_pages():
    body = client.get("/llms.txt").text
    for page in PAGES:
        if not page.indexable:
            assert page.path not in body


def test_llms_names_active_integrations_only():
    body = client.get("/llms.txt").text
    for name in ("ElevenLabs", "Google Calendar", "Google Sheets"):
        assert name in body
    for gone in ("OpenAI", "Twilio", "Vapi", "Outbound", "ROI"):
        assert gone not in body
