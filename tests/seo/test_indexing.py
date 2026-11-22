"""Crawl/index controls: X-Robots-Tag, root redirect, and docs exposure (SEO.5)."""

import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import LANDING_PATH, app, create_app
from app.seo.registry import PAGES

client = TestClient(app)

INDEXABLE = [p for p in PAGES if p.indexable]
NOINDEX = [p for p in PAGES if not p.indexable]
APP = "/automiteaiapplication"
DOC_PATHS = [f"{APP}/docs", f"{APP}/redoc", f"{APP}/openapi.json"]


def _meta_robots(html: str) -> str:
    head = html[: html.index("</head>")]
    return re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', head).group(1)


@pytest.mark.parametrize("page", NOINDEX, ids=lambda p: p.template)
def test_noindex_pages_send_x_robots_tag_matching_meta(page):
    r = client.get(page.path)
    assert r.status_code == 200
    assert r.headers.get_list("x-robots-tag") == [_meta_robots(r.text)]


@pytest.mark.parametrize("page", NOINDEX, ids=lambda p: p.template)
def test_noindex_header_contains_noindex(page):
    assert "noindex" in client.get(page.path).headers["x-robots-tag"]


def test_preview_is_noindex_nofollow():
    page = next(p for p in PAGES if p.page_type == "preview")
    assert client.get(page.path).headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize("page", INDEXABLE, ids=lambda p: p.template)
def test_indexable_pages_have_no_x_robots_tag(page):
    assert "x-robots-tag" not in client.get(page.path).headers


def test_root_is_single_301_hop_to_landing():
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == LANDING_PATH
    final = client.get(r.headers["location"], follow_redirects=False)
    assert final.status_code == 200
    assert LANDING_PATH in {p.path for p in INDEXABLE}


def test_root_redirect_followed_has_exactly_one_hop():
    r = client.get("/", follow_redirects=True)
    assert [h.status_code for h in r.history] == [301]
    assert r.status_code == 200


@pytest.mark.parametrize("app_env, exposed", [("production", False), ("development", True)])
def test_docs_exposure_follows_environment(monkeypatch, app_env, exposed):
    monkeypatch.setattr(settings, "app_env", app_env)
    c = TestClient(create_app())
    for path in DOC_PATHS:
        assert (c.get(path).status_code == 200) is exposed, path
