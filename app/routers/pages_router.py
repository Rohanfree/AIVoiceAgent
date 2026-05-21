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


templates.env.globals["static_hash"] = _static_hash

router = APIRouter(
    prefix="/pages",
    tags=["Pages"],
)


@router.get("/landing", response_class=HTMLResponse, summary="Landing page")
async def landing_page(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/login", response_class=HTMLResponse, summary="Client login page")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse, summary="Client registration page")
async def register_page(request: Request):
    from zoneinfo import available_timezones
    timezones = sorted(available_timezones())
    return templates.TemplateResponse("register.html", {"request": request, "timezones": timezones})


@router.get("/dashboard", response_class=HTMLResponse, summary="Client dashboard page")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get(
    "/mngr-sys-access-78",
    response_class=HTMLResponse,
    summary="Admin login page",
    include_in_schema=False,
)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})


@router.get(
    "/mngr-sys-access-78/dashboard",
    response_class=HTMLResponse,
    summary="Admin dashboard page",
    include_in_schema=False,
)
async def admin_dashboard_page(request: Request):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})
