"""
extraction_router.py — Placeholder endpoints for the Intelligent Extraction Engine.

All endpoints return a "coming soon" response. The actual LLM-powered extraction
logic will be implemented in a future release. See README.md for details.

Context path: /automiteui/extraction/*
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/extraction",
    tags=["Extraction Engine (Beta)"],
)

_COMING_SOON = {
    "status": "coming_soon",
    "message": (
        "The Intelligent Extraction Engine is under development. "
        "This feature will use an LLM to parse brochures and documents "
        "into structured service data. Check the README for the roadmap."
    ),
}


@router.post(
    "/parse-text",
    summary="[Beta] Parse brochure text into structured data",
)
async def parse_text() -> dict:
    """Placeholder — will accept raw text and return extracted services via LLM."""
    return _COMING_SOON


@router.post(
    "/upload-file",
    summary="[Beta] Upload a document for extraction",
)
async def upload_file() -> dict:
    """Placeholder — will accept PDF/image uploads, OCR, and extract services."""
    return _COMING_SOON


@router.post(
    "/confirm",
    summary="[Beta] Confirm and save extracted data",
)
async def confirm_extraction() -> dict:
    """Placeholder — will accept edited extraction results and commit to Firestore."""
    return _COMING_SOON
