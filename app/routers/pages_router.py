"""
pages_router.py — Serves Jinja2 HTML pages under /automiteui/pages/*.

These are server-rendered pages for the Automite AI dashboard UI.
API calls from the pages are handled by the other routers (auth, client-portal, admin).
"""

import hashlib
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.seo.registry import PAGES, UI_PREFIX

_PAGES_BY_TEMPLATE = {p.template: p for p in PAGES}

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")


def _static_hash(relative_path: str) -> str:
    """Return an 8-char MD5 of the file's contents for cache-busting."""
    full = os.path.join("app/static", relative_path)
    try:
        digest = hashlib.md5(open(full, "rb").read()).hexdigest()[:8]
        return digest
    except OSError:
        return "0"


def _seo_page(template: str):
    page = _PAGES_BY_TEMPLATE.get(template)
    if page is None:
        raise KeyError(f"No SEO registry entry for template {template!r}")
    return page


def _robots_headers(template: str) -> dict[str, str]:
    """X-Robots-Tag for noindex pages, mirroring the template's robots meta tag.

    Admin and preview pages are noindex,nofollow; other private pages keep
    noindex,follow. Indexable pages get no header.
    """
    page = _seo_page(template)
    if page.indexable:
        return {}
    follow = "nofollow" if page.page_type in ("admin", "preview") else "follow"
    return {"X-Robots-Tag": f"noindex, {follow}"}


def _site_url() -> str:
    """Configured public origin (no trailing slash), read at render time."""
    return settings.public_site_url.rstrip("/")


templates.env.globals["static_hash"] = _static_hash
templates.env.globals["seo_page"] = _seo_page
templates.env.globals["site_url"] = _site_url
templates.env.globals["ui_prefix"] = UI_PREFIX

router = APIRouter(
    prefix="/pages",
    tags=["Pages"],
)


@router.get("/landing", response_class=HTMLResponse, summary="Landing page")
async def landing_page(request: Request):
    return templates.TemplateResponse(
        "landing.html",
        {"request": request, "seo_template": "landing.html"},
    )


@router.get(
    "/landing-moves-preview",
    response_class=HTMLResponse,
    summary="Design prototype preview (not linked from live pages)",
    include_in_schema=False,
)
async def landing_moves_preview(request: Request):
    # Belt-and-braces noindex: meta tag in the template + HTTP header here
    # (headers survive even if a crawler ignores meta tags).
    return templates.TemplateResponse(
        "landing_moves_preview.html",
        {"request": request},
        headers=_robots_headers("landing_moves_preview.html"),
    )


@router.get("/case-studies", response_class=HTMLResponse, summary="Case studies page")
async def case_studies_page(request: Request):
    return templates.TemplateResponse(
        "case-studies.html",
        {"request": request, "seo_template": "case-studies.html"},
    )


@router.get("/privacy-policy", response_class=HTMLResponse, summary="Privacy policy page")
async def privacy_policy_page(request: Request):
    return templates.TemplateResponse(
        "privacy-policy.html",
        {"request": request, "seo_template": "privacy-policy.html"},
    )


@router.get("/login", response_class=HTMLResponse, summary="Client login page")
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "seo_template": "login.html"},
        headers=_robots_headers("login.html"),
    )


@router.get("/register", response_class=HTMLResponse, summary="Client registration page")
async def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "seo_template": "register.html"},
        headers=_robots_headers("register.html"),
    )


@router.get("/dashboard", response_class=HTMLResponse, summary="Client dashboard page")
async def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "seo_template": "dashboard.html"},
        headers=_robots_headers("dashboard.html"),
    )


@router.get(
    "/mngr-sys-access-78",
    response_class=HTMLResponse,
    summary="Admin login page",
    include_in_schema=False,
)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request, "seo_template": "admin/login.html"},
        headers=_robots_headers("admin/login.html"),
    )


@router.get(
    "/mngr-sys-access-78/dashboard",
    response_class=HTMLResponse,
    summary="Admin dashboard page",
    include_in_schema=False,
)
async def admin_dashboard_page(request: Request):
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "seo_template": "admin/dashboard.html"},
        headers=_robots_headers("admin/dashboard.html"),
    )
