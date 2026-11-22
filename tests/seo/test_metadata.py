"""Rendered head metadata for every registered page (SEO.3)."""

import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.seo.registry import PAGES

client = TestClient(app)

INDEXABLE = [p for p in PAGES if p.indexable]
NOINDEX = [p for p in PAGES if not p.indexable]
ADMIN = [p for p in NOINDEX if p.page_type == "admin"]


def _get(path: str) -> str:
    r = client.get(path)
    assert r.status_code == 200, path
    return r.text


def _head(html: str) -> str:
    return html[: html.index("</head>")]


def _meta_count(head: str, attr: str, key: str) -> int:
    return len(re.findall(rf'<meta\s+{attr}="{re.escape(key)}"', head))


def _robots(head: str) -> list[str]:
    return re.findall(r'<meta\s+name="robots"\s+content="([^"]*)"', head)


@pytest.mark.parametrize("page", INDEXABLE, ids=lambda p: p.template)
def test_indexable_head_has_exactly_one_of_each(page):
    html = _get(page.path)
    head = _head(html)
    site = settings.public_site_url.rstrip("/")
    canonical = f"{site}{page.path}"

    assert len(re.findall(r"<title>", head)) == 1
    assert f"<title>{page.title}</title>" in head
    assert _meta_count(head, "name", "description") == 1
    assert re.findall(r'<link\s+rel="canonical"\s+href="([^"]*)"', head) == [canonical]
    assert re.findall(r'<meta\s+property="og:url"\s+content="([^"]*)"', head) == [canonical]
    assert _meta_count(head, "property", "og:title") == 1
    assert _meta_count(head, "property", "og:description") == 1
    assert _meta_count(head, "name", "twitter:title") == 1
    assert head.count('type="application/ld+json"') == 1
    assert not any("noindex" in r for r in _robots(head))
    assert len(re.findall(r"<h1[\s>]", html)) == 1


@pytest.mark.parametrize("page", INDEXABLE, ids=lambda p: p.template)
def test_indexable_description_matches_registry(page):
    from html import unescape

    head = _head(_get(page.path))
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', head)
    assert unescape(m.group(1)) == page.description


@pytest.mark.parametrize("page", INDEXABLE, ids=lambda p: p.template)
def test_indexable_pages_follow_configured_public_site_url(page, monkeypatch):
    monkeypatch.setattr(settings, "public_site_url", "https://staging.example.test/")
    head = _head(_get(page.path))
    assert f'href="https://staging.example.test{page.path}"' in head
    assert f'content="https://staging.example.test{page.path}"' in head
    assert "auto-mite.com" not in head


def test_jsonld_is_valid_json_with_configured_host(monkeypatch):
    import json

    monkeypatch.setattr(settings, "public_site_url", "https://staging.example.test")
    for page in INDEXABLE:
        head = _head(_get(page.path))
        raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S).group(1)
        graph = json.loads(raw)["@graph"]
        types = [n["@type"] for n in graph]
        assert types[:2] == ["Organization", "WebSite"]
        assert "auto-mite.com" not in raw
    landing = json.loads(
        re.search(r'ld\+json">(.*?)</script>', _head(_get(INDEXABLE[0].path)), re.S).group(1)
    )["@graph"]
    assert [n["@type"] for n in landing] == ["Organization", "WebSite", "Service", "FAQPage"]


@pytest.mark.parametrize("page", NOINDEX, ids=lambda p: p.template)
def test_noindex_pages_keep_noindex_signal(page):
    if page.page_type == "preview":
        # Prototype page: meta tag plus X-Robots-Tag header.
        r = client.get(page.path)
        assert r.headers["x-robots-tag"] == "noindex, nofollow"
        assert any("noindex" in x for x in _robots(_head(r.text)))
        return
    head = _head(_get(page.path))
    robots = _robots(head)
    assert len(robots) == 1 and "noindex" in robots[0]
    assert len(re.findall(r"<title>", head)) == 1
    assert 'rel="canonical"' not in head
    assert 'property="og:url"' not in head


@pytest.mark.parametrize("page", ADMIN, ids=lambda p: p.template)
def test_admin_pages_are_noindex_nofollow(page):
    assert _robots(_head(_get(page.path))) == ["noindex, nofollow"]


@pytest.mark.parametrize("page", [p for p in NOINDEX if p.page_type in ("auth", "dashboard")], ids=lambda p: p.template)
def test_private_pages_keep_noindex_follow(page):
    assert _robots(_head(_get(page.path))) == ["noindex, follow"]
