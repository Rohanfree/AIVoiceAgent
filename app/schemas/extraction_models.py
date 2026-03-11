"""
extraction_models.py — Pydantic schemas for the Intelligent Extraction Engine (Beta).

These models define the structure for extracted service data.
Currently used as schema definitions only; the LLM extraction pipeline
is planned for a future release.
"""

from pydantic import BaseModel, Field


class ExtractedService(BaseModel):
    """A single service extracted from a brochure or document."""

    service_name: str = Field(..., max_length=64, description="Name of the service or product")
    price: float | None = Field(default=None, description="Monetary value; null if not found")
    timing: str | None = Field(default=None, description="Operating time in ISO 8601 or 24hr format")
    description: str | None = Field(default=None, description="Brief description of the service")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")


class ExtractionRequest(BaseModel):
    """Request body for submitting text for extraction."""

    raw_text: str = Field(..., min_length=10, description="Raw brochure or document text to parse")


class ExtractionResponse(BaseModel):
    """Response containing extracted service data."""

    services: list[ExtractedService] = Field(default_factory=list)
    source_text_length: int = 0
    model_used: str = "pending"
    is_draft: bool = True
