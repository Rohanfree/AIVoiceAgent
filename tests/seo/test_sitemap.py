"""sitemap.xml index and sitemap-pages.xml contents (SEO.4)."""

import re

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seo.registry import PAGES, indexable_pages

client = TestClient(app)
BASE = settings.public_site_url.rstrip("/")


def _locs(xml: str) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def test_index_references_pages_and_separate_blog_sitemap():
    xml = client.get("/sitemap.xml").text
    assert "<sitemapindex" in xml
    assert _locs(xml) == [f"{BASE}/sitemap-pages.xml", f"{BASE}/blogs/sitemap.xml"]


def test_pages_sitemap_lists_exactly_indexable_registry_pages():
    locs = _locs(client.get("/sitemap-pages.xml").text)
    assert locs == [f"{BASE}{p.path}" for p in indexable_pages()]


def test_pages_sitemap_excludes_noindex_and_blog():
    xml = client.get("/sitemap-pages.xml").text
    for page in PAGES:
        if not page.indexable:
            assert page.path not in xml
    assert "/blogs" not in xml


def test_no_invented_lastmod_or_hints():
    for path in ("/sitemap.xml", "/sitemap-pages.xml"):
        xml = client.get(path).text
        assert "<lastmod>" not in xml  # registry has no real lastmod values
        assert "<changefreq>" not in xml
        assert "<priority>" not in xml


def test_lastmod_emitted_only_from_registry(monkeypatch):
    import dataclasses

    from app.routers import seo_router

    pages = tuple(
        dataclasses.replace(p, lastmod="2026-01-02") if p.indexable else p for p in PAGES
    )
    monkeypatch.setattr(seo_router, "indexable_pages", lambda: tuple(p for p in pages if p.indexable))
    xml = client.get("/sitemap-pages.xml").text
    assert xml.count("<lastmod>2026-01-02</lastmod>") == len(indexable_pages())
