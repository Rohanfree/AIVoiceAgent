"""
main.py - FastAPI application entry point.

Sets up:
  - Logging (verbose in development, concise in production)
  - CORS middleware
  - Existing routes: /agent-tools
  - New routes under /automiteui: /auth, /client-portal, /mngr-sys-access-78,
    /extraction, /pages
  - Static file serving at /automiteui/static
  - Health check endpoint
  - Debug request/response middleware (prints full JSON when APP_ENV=development)
"""

import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Callable

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
# NOTE: agent_tools (VAPI) router has been moved to app/legacy/vapi/ and is no longer registered.

# Mount prefix for the server-rendered UI (single source of truth — the
# root redirect below derives the landing URL from it so it stays correct
# if the prefix ever moves).
UI_PREFIX = "/automiteaiapplication/automiteui"
LANDING_PATH = f"{UI_PREFIX}/pages/landing"

# ─── Logging setup ─────────────────────────────────────────────────────────

def _configure_logging() -> None:
    """
    Configure root logger.
    - development → DEBUG level with detailed formatter
    - production  → INFO level with concise formatter
    """
    log_level = logging.DEBUG if settings.debug else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        if settings.debug
        else "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers in production
    if not settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("google.auth").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)


# ─── Usage limit background checker ────────────────────────────────────────

async def _check_usage_limits() -> None:
    """
    Check every active client that has a monthly_character_limit set.
    If their ElevenLabs usage for the current calendar month meets or exceeds
    the limit, deactivate them (Firestore + agent prompt override).
    Runs 5 times per day (every ~5 hours).
    """
    from app.db import get_db
    from app.services.elevenlabs_service import get_agent_usage, deactivate_agent_prompt

    logger.info("Usage-limit checker: starting run")
    checked = deactivated = 0
    try:
        db = get_db()
        now = datetime.now(tz=timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_unix = int(month_start.timestamp())
        end_unix = int(now.timestamp())

        from google.cloud.firestore import FieldFilter
        docs = list(
            db.collection("clients").where(
                filter=FieldFilter("is_active", "==", True)
            ).stream()
        )
        logger.info("Usage-limit checker: %d active client(s) to check", len(docs))

    except Exception as exc:
        logger.error("Usage-limit checker: failed to load clients — %s", exc)
        return

    for doc in docs:
        client_id = doc.id
        try:
            data = doc.to_dict() or {}
            limit = data.get("monthly_character_limit")
            if not limit:
                continue  # no limit set — skip

            agent_id = data.get("elevenlabs_agent_id")
            if not agent_id:
                continue

            checked += 1
            usage = await get_agent_usage(agent_id, start_unix, end_unix, summary_only=True)
            used = usage.get("total_characters", 0)
            name = data.get("business_name", client_id)
            logger.info(
                "Usage-limit checker: %s — %d / %d chars used (%.1f%%)",
                name, used, limit, 100 * used / limit,
            )

            if used >= limit:
                logger.warning(
                    "Usage-limit checker: %s exceeded limit — deactivating", name,
                )
                db.collection("clients").document(client_id).set(
                    {
                        "is_active": False,
                        "deactivation_reason": "limit_exceeded",
                        "updated_at": now.isoformat(),
                    },
                    merge=True,
                )
                await deactivate_agent_prompt(agent_id, client_id)
                deactivated += 1

        except Exception as exc:
            logger.error("Usage-limit checker: error processing client %s — %s", client_id, exc)

    logger.info(
        "Usage-limit checker: run complete — %d checked, %d deactivated",
        checked, deactivated,
    )


async def _usage_limit_loop() -> None:
    """Background loop — runs _check_usage_limits every 5 hours."""
    # Wait 60 s after startup before the first check so the app is fully ready
    await asyncio.sleep(60)
    while True:
        await _check_usage_limits()
        await asyncio.sleep(5 * 60 * 60)  # 5 hours


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_usage_limit_loop())
    logger.info("Usage-limit background checker started (interval: 5 h)")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Usage-limit background checker stopped")


# ─── App factory ───────────────────────────────────────────────────────────

_NON_SECRET_TOKEN_KEYS = {"tokens_revoked", "token_id", "tool_token_id"}
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-client-token"}


def _is_secret_key(key) -> bool:
    k = str(key).lower()
    return "password" in k or ("token" in k and k not in _NON_SECRET_TOKEN_KEYS)


def _redact_headers(headers) -> dict:
    return {k: "***REDACTED***" if k.lower() in _SENSITIVE_HEADERS else v for k, v in headers.items()}


def _redact_passwords(value):
    """Return a copy of parsed JSON with password/token fields masked, for debug logging."""
    if isinstance(value, dict):
        return {
            k: "***REDACTED***" if _is_secret_key(k) else _redact_passwords(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_passwords(v) for v in value]
    return value


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    app = FastAPI(
        lifespan=lifespan,
        title="Automite AI — Intelligent Automation Platform",
        description=(
            "Backend API for the Automite AI ecosystem. Includes client portal, "
            "admin dashboard, and intelligent extraction tools. "
            "All features are served under the /automiteui context path."
        ),
        version="2.0.0",
        # Interactive API docs are exposed only in development.
        docs_url="/automiteaiapplication/docs" if settings.debug else None,
        redoc_url="/automiteaiapplication/redoc" if settings.debug else None,
        openapi_url="/automiteaiapplication/openapi.json" if settings.debug else None,
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Debug middleware ─────────────────────────────────────────────────────
    if settings.debug:
        @app.middleware("http")
        async def debug_request_response_middleware(
            request: Request, call_next: Callable
        ) -> Response:
            """
            When APP_ENV=development, log:
            - Incoming request method, URL, headers, and body.
            - Outgoing response status code, headers, and body.
            - Request processing time in milliseconds.
            """
            # --- Request logging ---
            req_body_bytes = await request.body()
            try:
                req_body_str = json.dumps(
                    _redact_passwords(json.loads(req_body_bytes)), indent=2
                ) if req_body_bytes else "(empty)"
            except (json.JSONDecodeError, ValueError):
                # Non-JSON bodies (e.g. forms) may carry passwords; don't log them verbatim.
                req_body_str = "(non-JSON body omitted)"

            logger.debug(
                "\n━━━ INCOMING REQUEST ━━━\n"
                "%s %s\n"
                "Headers: %s\n"
                "Body:\n%s",
                request.method,
                request.url,
                _redact_headers(request.headers),
                req_body_str,
            )

            start_time = time.perf_counter()

            # Re-inject body so downstream handlers can read it
            async def receive():
                return {"type": "http.request", "body": req_body_bytes}

            request = Request(request.scope, receive)

            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1_000

            # --- Response logging ---
            resp_body = b""
            async for chunk in response.body_iterator:
                resp_body += chunk

            try:
                resp_body_str = json.dumps(
                    _redact_passwords(json.loads(resp_body)), indent=2
                )
            except (json.JSONDecodeError, ValueError):
                resp_body_str = "(non-JSON body omitted)" if resp_body else "(empty)"

            logger.debug(
                "\n━━━ OUTGOING RESPONSE ━━━\n"
                "Status: %d | Time: %.2f ms\n"
                "Body:\n%s",
                response.status_code,
                elapsed_ms,
                resp_body_str,
            )

            # Return a new Response with the consumed body
            return Response(
                content=resp_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

    # ── Routers — all under /automiteui parent prefix ───────────────────────
    # NOTE: VAPI agent-tools router removed — see app/legacy/vapi/agent_tools.py
    from app.routers import (
        admin_router,
        agent_tools_elevenlabs,
        auth_router,
        campaign_router,
        client_router,
        contact_router,
        extraction_router,
        pages_router,
        google_auth_router,
        seo_router,
    )

    app.include_router(auth_router.router, prefix=UI_PREFIX)
    app.include_router(client_router.router, prefix=UI_PREFIX)
    app.include_router(campaign_router.router, prefix=UI_PREFIX)
    app.include_router(admin_router.router, prefix=UI_PREFIX)
    app.include_router(extraction_router.router, prefix=UI_PREFIX)
    app.include_router(pages_router.router, prefix=UI_PREFIX)
    app.include_router(google_auth_router.router, prefix="/automiteaiapplication")
    app.include_router(contact_router.router, prefix=UI_PREFIX)
    app.include_router(agent_tools_elevenlabs.router, prefix="/automiteaiapplication")
    app.include_router(seo_router.router)  # /robots.txt, sitemaps, /llms.txt at site root

    # ── Static files ────────────────────────────────────────────────────────
    app.mount(
        "/automiteaiapplication/automiteui/static",
        StaticFiles(directory="app/static"),
        name="static",
    )

    # ── Health check ────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False, summary="Redirect bare root to landing")
    async def root() -> RedirectResponse:
        """Bare / 301-redirects to the landing page (derived from UI_PREFIX)."""
        return RedirectResponse(url=LANDING_PATH, status_code=301)

    @app.get("/automiteaiapplication/health", tags=["Health"], summary="Service health check")
    async def health() -> dict:
        """Returns a simple liveness signal and current environment."""
        return {"status": "ok", "environment": settings.app_env, "version": "2.0.0"}

    logger.info(
        "Automite AI API started | env=%s | debug=%s | version=2.0.0",
        settings.app_env,
        settings.debug,
    )

    return app


app = create_app()

# ─── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,   # Hot-reload only in development
        log_level="debug" if settings.debug else "info",
    )

