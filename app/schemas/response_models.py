"""
response_models.py - Pydantic response schemas for all /agent-tools endpoints.
"""

from typing import Any

from pydantic import BaseModel, Field


# ─── GET CLIENT BY MOBILE ────────────────────────────────────────────────────

class CustomerFoundResponse(BaseModel):
    """Returned when a customer record is located."""

    found: bool = True
    customer_name: str
    last_visit: str | None = None
    notes: str | None = None


class CustomerNotFoundResponse(BaseModel):
    """Returned when no matching customer is found."""

    found: bool = False


# ─── GET SERVICES AND PRICES ─────────────────────────────────────────────────

class ServiceItem(BaseModel):
    """A single service offered by the business client."""

    name: str
    duration: int = Field(..., description="Duration of service in minutes")
    price: float


class GetServicesResponse(BaseModel):
    """Response containing all services and prices for a client."""

    services: list[ServiceItem]


# ─── CHECK AVAILABILITY ──────────────────────────────────────────────────────

class AvailableResponse(BaseModel):
    """Returned when the requested time slot is free."""

    available: bool = True


class UnavailableResponse(BaseModel):
    """Returned when the requested slot is taken; includes next free slot."""

    available: bool = False
    next_available: str = Field(..., description="Next available ISO time slot")


# ─── BOOK APPOINTMENT ────────────────────────────────────────────────────────

class BookingStatusResponse(BaseModel):
    """Generic booking status response."""

    status: str = Field(..., description='"confirmed" or "failed"')


# ─── SAVE CALL LOG ───────────────────────────────────────────────────────────

class SaveCallLogResponse(BaseModel):
    """Returned after persisting a call log entry."""

    status: str = Field(default="saved")


# ─── ERROR ───────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Generic error response body."""

    detail: str
