"""Tests for the SEO page registry (app/seo/registry.py)."""

import re
from pathlib import Path

import pytest
from fastapi.responses import HTMLResponse

from app.config import Settings
from app.main import UI_PREFIX
from app.routers import pages_router
from app.seo import registry
from app.seo.registry import PAGES, PAGES_BY_PATH, get_page, indexable_pages

TEMPLATES = Path("app/templates")


def _html_route_paths() -> set[str]:
    return {
        UI_PREFIX + r.path
        for r in pages_router.router.routes
        if r.response_class is HTMLResponse
    }


def test_prefix_matches_app():
    assert registry.UI_PREFIX == UI_PREFIX


def test_every_html_route_is_registered():
    assert _html_route_paths() == set(PAGES_BY_PATH)


def test_paths_unique_and_templates_exist():
    assert len(PAGES_BY_PATH) == len(PAGES)
    for page in PAGES:
        assert (TEMPLATES / page.template).is_file(), page.template


def test_page_types_valid():
    assert {p.page_type for p in PAGES} <= set(registry.PAGE_TYPES)


def test_public_pages_indexable():
    assert {p.path.rsplit("/", 1)[-1] for p in indexable_pages()} == {
        "landing",
        "case-studies",
        "privacy-policy",
    }
    for page in indexable_pages():
        assert page.canonical_path == page.path
        assert page.title and page.description


@pytest.mark.parametrize("page_type", ["auth", "dashboard", "admin", "preview"])
def test_private_surfaces_not_indexable(page_type):
    pages = [p for p in PAGES if p.page_type == page_type]
    assert pages
    for page in pages:
        assert page.indexable is False
        assert page.canonical_path is None


def test_noindex_pages_match_template_robots_meta():
    for page in PAGES:
        source = (TEMPLATES / page.template).read_text()
        noindex = re.search(r'name="robots"\s+content="[^"]*noindex', source) is not None
        assert noindex == (not page.indexable), page.path


def test_lastmod_not_invented():
    assert all(p.lastmod is None for p in PAGES)


def test_get_page():
    assert get_page(f"{UI_PREFIX}/pages/landing").template == "landing.html"
    assert get_page("/nope") is None


def test_public_site_url_separate_from_base_url():
    s = Settings(_env_file=None)
    assert s.public_site_url == "https://auto-mite.com"
    assert s.base_url == "http://localhost:8090"
