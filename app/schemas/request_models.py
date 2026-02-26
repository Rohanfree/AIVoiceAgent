"""
request_models.py - Pydantic request body schemas for all /agent-tools endpoints.
"""

from pydantic import BaseModel, Field


# ─── GET CLIENT BY MOBILE ────────────────────────────────────────────────────

class GetClientByMobileRequest(BaseModel):
    """Request schema for POST /agent-tools/get-client-by-mobile"""

    client_id: str = Field(..., description="The unique ID of the business client")
    customer_phone: str = Field(..., description="Customer phone number to search by")


# ─── GET SERVICES AND PRICES ─────────────────────────────────────────────────

class GetServicesRequest(BaseModel):
    """Request schema for POST /agent-tools/get-services-and-prices"""

    client_id: str = Field(..., description="The unique ID of the business client")


# ─── CHECK AVAILABILITY ──────────────────────────────────────────────────────

class CheckAvailabilityRequest(BaseModel):
    """Request schema for POST /agent-tools/check-availability"""

    client_id: str = Field(..., description="The unique ID of the business client")
    service_name: str = Field(..., description="Name of the service being requested")
    date_time: str = Field(
        ...,
        description="Desired appointment start time in ISO 8601 format (e.g. 2024-06-01T10:00:00)",
    )


# ─── BOOK APPOINTMENT ────────────────────────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    """Request schema for POST /agent-tools/book-appointment"""

    client_id: str = Field(..., description="The unique ID of the business client")
    customer_name: str = Field(..., description="Full name of the customer")
    customer_phone: str = Field(..., description="Phone number of the customer")
    service_name: str = Field(..., description="Name of the service to book")
    date_time: str = Field(
        ...,
        description="Appointment start time in ISO 8601 format",
    )


# ─── SAVE CALL LOG ───────────────────────────────────────────────────────────

class SaveCallLogRequest(BaseModel):
    """Request schema for POST /agent-tools/save-call-log"""

    client_id: str = Field(..., description="The unique ID of the business client")
    caller_phone: str = Field(..., description="Phone number of the caller")
    transcript: str = Field(..., description="Full call transcript text")
    summary: str = Field(..., description="Short summary of the call")
    extracted_customer_name: str | None = Field(
        default=None,
        description="Customer name extracted from the conversation, if available",
    )
