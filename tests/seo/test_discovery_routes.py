"""Discovery routes live in seo_router and are served from the site root (SEO.4)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ROUTES = {
    "/robots.txt": "text/plain",
    "/sitemap.xml": "application/xml",
    "/sitemap-pages.xml": "application/xml",
    "/llms.txt": "text/plain",
}


@pytest.mark.parametrize("path,ctype", ROUTES.items())
def test_route_served_with_content_type(path, ctype):
    r = client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(ctype)


@pytest.mark.parametrize("path", ROUTES)
def test_route_defined_in_seo_router_and_hidden_from_schema(path):
    from app.routers import seo_router

    matches = [r for r in seo_router.router.routes if r.path == path]
    assert len(matches) == 1
    assert matches[0].include_in_schema is False
    assert path not in app.openapi()["paths"]


def test_public_site_url_drives_all_urls(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "public_site_url", "https://example.test/")
    for path in ROUTES:
        body = client.get(path).text
        assert "https://example.test" in body
        assert "auto-mite.com" not in body
        assert "example.test//" not in body
