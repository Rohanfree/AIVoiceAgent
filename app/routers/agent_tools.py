"""
agent_tools.py - APIRouter for all /agent-tools endpoints.

Each route is an async FastAPI endpoint that:
  1. Accepts a typed Pydantic request body.
  2. Delegates business logic to a service module.
  3. Returns a typed Pydantic response.
  4. Emits debug-level request/response logs when APP_ENV=development.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client

from app.config import settings
from app.db import get_db
from app.schemas.request_models import (
    BookAppointmentRequest,
    CheckAvailabilityRequest,
    GetClientByMobileRequest,
    GetServicesRequest,
    SaveCallLogRequest,
)
from app.schemas.response_models import (
    AvailableResponse,
    BookingStatusResponse,
    CustomerFoundResponse,
    CustomerNotFoundResponse,
    GetServicesResponse,
    SaveCallLogResponse,
    ServiceItem,
    UnavailableResponse,
)
from app.services.availability_service import (
    check_slot_availability,
    get_service_duration,
)
from app.services.booking_service import (
    create_appointment,
    find_service,
    get_client_services,
    save_call_log,
)
from app.services.customer_service import get_customer_by_phone, upsert_customer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-tools", tags=["Agent Tools"])


# ─── Debug logging helpers ─────────────────────────────────────────────────

def _debug_request(endpoint: str, body: Any) -> None:
    """Log request payload when debug mode is active."""
    if settings.debug:
        logger.debug(
            "[REQUEST] %s\n%s",
            endpoint,
            json.dumps(body.model_dump(), indent=2, default=str),
        )


def _debug_response(endpoint: str, response: Any) -> None:
    """Log response payload when debug mode is active."""
    if settings.debug:
        payload = (
            response.model_dump()
            if hasattr(response, "model_dump")
            else response
        )
        logger.debug(
            "[RESPONSE] %s\n%s",
            endpoint,
            json.dumps(payload, indent=2, default=str),
        )


# ─── A) GET CLIENT BY MOBILE ───────────────────────────────────────────────

@router.post(
    "/get-client-by-mobile",
    response_model=Union[CustomerFoundResponse, CustomerNotFoundResponse],
    summary="Look up a customer by phone number",
    description=(
        "Searches the customers collection using client_id + customer_phone. "
        "Returns customer details if found, or {found: false} otherwise."
    ),
)
async def get_client_by_mobile(
    request: GetClientByMobileRequest,
    db: Client = Depends(get_db),
) -> CustomerFoundResponse | CustomerNotFoundResponse:
    _debug_request("/agent-tools/get-client-by-mobile", request)

    customer = get_customer_by_phone(
        db=db,
        client_id=request.client_id,
        phone=request.customer_phone,
    )

    if customer:
        resp = CustomerFoundResponse(
            found=True,
            customer_name=customer.get("name", ""),
            last_visit=customer.get("last_visit"),
            notes=customer.get("notes"),
        )
    else:
        resp = CustomerNotFoundResponse(found=False)

    _debug_response("/agent-tools/get-client-by-mobile", resp)
    return resp


# ─── B) GET SERVICES AND PRICES ─────────────────────────────────────────────

@router.post(
    "/get-services-and-prices",
    response_model=GetServicesResponse,
    summary="Retrieve services and pricing for a client",
    description="Fetches the services array from the client document in Firestore.",
)
async def get_services_and_prices(
    request: GetServicesRequest,
    db: Client = Depends(get_db),
) -> GetServicesResponse:
    _debug_request("/agent-tools/get-services-and-prices", request)

    services_raw = get_client_services(db=db, client_id=request.client_id)

    if services_raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{request.client_id}' not found.",
        )

    services = [
        ServiceItem(
            name=svc.get("name", ""),
            duration=int(svc.get("duration", 0)),
            price=float(svc.get("price", 0.0)),
        )
        for svc in services_raw
    ]

    resp = GetServicesResponse(services=services)
    _debug_response("/agent-tools/get-services-and-prices", resp)
    return resp


# ─── C) CHECK AVAILABILITY ──────────────────────────────────────────────────

@router.post(
    "/check-availability",
    response_model=Union[AvailableResponse, UnavailableResponse],
    summary="Check whether an appointment slot is free",
    description=(
        "Fetches service duration, then checks appointments collection for "
        "overlapping bookings. Returns available=true or next_available time."
    ),
)
async def check_availability(
    request: CheckAvailabilityRequest,
    db: Client = Depends(get_db),
) -> AvailableResponse | UnavailableResponse:
    _debug_request("/agent-tools/check-availability", request)

    # Resolve service duration
    duration = get_service_duration(
        db=db,
        client_id=request.client_id,
        service_name=request.service_name,
    )
    if duration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Service '{request.service_name}' not found "
                f"for client '{request.client_id}'."
            ),
        )

    # Parse requested datetime
    try:
        requested_dt = datetime.fromisoformat(request.date_time)
        if requested_dt.tzinfo is None:
            requested_dt = requested_dt.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date_time format: {exc}",
        ) from exc

    is_available, next_available = check_slot_availability(
        db=db,
        client_id=request.client_id,
        service_name=request.service_name,
        requested_dt=requested_dt,
        duration_minutes=duration,
    )

    if is_available:
        resp: AvailableResponse | UnavailableResponse = AvailableResponse(available=True)
    else:
        resp = UnavailableResponse(available=False, next_available=next_available or "")

    _debug_response("/agent-tools/check-availability", resp)
    return resp


# ─── D) BOOK APPOINTMENT ────────────────────────────────────────────────────

@router.post(
    "/book-appointment",
    response_model=BookingStatusResponse,
    summary="Book an appointment for a customer",
    description=(
        "Validates the service, persists the appointment, and upserts the "
        "customer record. Returns status='confirmed' or status='failed'."
    ),
)
async def book_appointment(
    request: BookAppointmentRequest,
    db: Client = Depends(get_db),
) -> BookingStatusResponse:
    _debug_request("/agent-tools/book-appointment", request)

    # Validate service exists
    services = get_client_services(db=db, client_id=request.client_id)
    if services is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{request.client_id}' not found.",
        )

    service = find_service(services, request.service_name)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Service '{request.service_name}' not found "
                f"for client '{request.client_id}'."
            ),
        )

    duration_minutes = int(service.get("duration", 0))

    success = create_appointment(
        db=db,
        client_id=request.client_id,
        customer_name=request.customer_name,
        customer_phone=request.customer_phone,
        service_name=request.service_name,
        date_time=request.date_time,
        duration_minutes=duration_minutes,
    )

    resp = BookingStatusResponse(status="confirmed" if success else "failed")
    _debug_response("/agent-tools/book-appointment", resp)
    return resp


# ─── E) SAVE CALL LOG ────────────────────────────────────────────────────────

@router.post(
    "/save-call-log",
    response_model=SaveCallLogResponse,
    summary="Persist a call log after the call ends",
    description=(
        "Saves a Retell AI call log to Firestore. If extracted_customer_name "
        "is provided, updates or creates the customer record."
    ),
)
async def save_call_log_endpoint(
    request: SaveCallLogRequest,
    db: Client = Depends(get_db),
) -> SaveCallLogResponse:
    _debug_request("/agent-tools/save-call-log", request)

    success = save_call_log(
        db=db,
        client_id=request.client_id,
        caller_phone=request.caller_phone,
        transcript=request.transcript,
        summary=request.summary,
        extracted_customer_name=request.extracted_customer_name,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save call log.",
        )

    resp = SaveCallLogResponse(status="saved")
    _debug_response("/agent-tools/save-call-log", resp)
    return resp
