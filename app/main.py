"""
main.py - FastAPI application entry point.

Sets up:
  - Logging (verbose in development, concise in production)
  - CORS middleware
  - /agent-tools router
  - Health check endpoint
  - Debug request/response middleware (prints full JSON when APP_ENV=development)
"""

import json
import logging
import sys
import time
from typing import Callable

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agent_tools, vapi_webhook

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

# ─── App factory ───────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""

    app = FastAPI(
        title="AI Receptionist Agent Tools API",
        description=(
            "Backend API for the AI Receptionist system integrated with Retell AI. "
            "Provides tools for checking availability, booking appointments, "
            "managing customers, and logging calls — all backed by Firebase Firestore."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    # Retell AI and any connected frontends will hit this API cross-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],        # Tighten in production with explicit origins
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
                    json.loads(req_body_bytes), indent=2
                ) if req_body_bytes else "(empty)"
            except (json.JSONDecodeError, ValueError):
                req_body_str = req_body_bytes.decode("utf-8", errors="replace") or "(empty)"

            logger.debug(
                "\n━━━ INCOMING REQUEST ━━━\n"
                "%s %s\n"
                "Headers: %s\n"
                "Body:\n%s",
                request.method,
                request.url,
                dict(request.headers),
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
                    json.loads(resp_body), indent=2
                )
            except (json.JSONDecodeError, ValueError):
                resp_body_str = resp_body.decode("utf-8", errors="replace") or "(empty)"

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

    # ── Routers ─────────────────────────────────────────────────────────────
    app.include_router(agent_tools.router)
    app.include_router(vapi_webhook.router)

    # ── Health check ────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Service health check")
    async def health() -> dict:
        """Returns a simple liveness signal and current environment."""
        return {"status": "ok", "environment": settings.app_env}

    logger.info(
        "AI Receptionist API started | env=%s | debug=%s",
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
