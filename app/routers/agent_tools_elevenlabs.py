"""
agent_tools_elevenlabs.py — ElevenLabs Conversational AI tool-call endpoints.

ElevenLabs calls these server-side webhooks during a conversation.
Each request is authenticated by an X-Client-Token header (JWT, scope="tool")
that encodes the client_id.

Routes (all POST, mounted at /automiteaiapplication/elevenlabs-tools):
  /get-customer
  /check-availability
  /book-appointment
  /save-call-summary
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from google.cloud.firestore import Client

from app.config import settings
from app.db import get_db
from app.services.availability_service import check_slot_availability
from app.services.booking_service import create_appointment, save_call_log
from app.services.calendar_service import create_calendar_event
from app.services.customer_service import get_customer_by_phone, get_last_call_summary
from app.services.sheets_service import append_call_to_sheet

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/elevenlabs-tools",
    tags=["ElevenLabs Tool Calls"],
)


def _log_tool_call(endpoint: str, request_body: dict, response: dict) -> None:
    if settings.agent_tools_debug:
        logger.info(
            "[agent-tool] %s | REQUEST: %s | RESPONSE: %s",
            endpoint,
            request_body,
            response,
        )


def _resolve_client_id(body: dict) -> str:
    """Extract client_id from the tool call request body (set by the agent's system prompt)."""
    client_id = (body.get("client_id") or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing client_id in request body.",
        )
    return client_id


# ─── GET CUSTOMER ────────────────────────────────────────────────────────────

@router.post("/get-customer", summary="Look up a caller by phone number")
async def get_customer(
    body: dict,
    db: Client = Depends(get_db),
) -> dict:
    """Return customer history for returning callers, or signal a new customer."""
    client_id = _resolve_client_id(body)
    phone = (body.get("customer_phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="customer_phone is required.")

    customer = get_customer_by_phone(db, client_id, phone)
    if not customer:
        result = {"found": False, "message": "New customer — no prior records."}
        _log_tool_call("get-customer", body, result)
        return result

    last_summary = get_last_call_summary(db, client_id, phone)
    result = {
        "found": True,
        "name": customer.get("name", "Unknown"),
        "phone": phone,
        "last_visit": customer.get("last_visit"),
        "notes": customer.get("notes"),
        "last_call_summary": last_summary,
    }
    _log_tool_call("get-customer", body, result)
    return result


# ─── CHECK AVAILABILITY ──────────────────────────────────────────────────────

@router.post("/check-availability", summary="Check if a slot is free")
async def check_availability(
    body: dict,
    db: Client = Depends(get_db),
) -> dict:
    """Return whether the requested time slot is available, and suggest the next free slot if not."""
    client_id = _resolve_client_id(body)
    service_name = (body.get("service_name") or "").strip()
    date_time_str = (body.get("date_time") or "").strip()

    if not service_name or not date_time_str:
        raise HTTPException(status_code=400, detail="service_name and date_time are required.")

    try:
        requested_dt = datetime.fromisoformat(date_time_str)
        if requested_dt.tzinfo is None:
            requested_dt = requested_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date_time format: {date_time_str}")

    duration = int(body.get("duration_minutes") or 30)

    is_available, next_slot = check_slot_availability(
        db=db,
        client_id=client_id,
        service_name=service_name,
        requested_dt=requested_dt,
        duration_minutes=duration,
    )

    if is_available:
        result = {"available": True, "message": "Slot is available."}
    else:
        result = {
            "available": False,
            "message": "Requested slot is taken.",
            "next_available": next_slot,
        }
    _log_tool_call("check-availability", body, result)
    return result


# ─── BOOK APPOINTMENT ────────────────────────────────────────────────────────

@router.post("/book-appointment", summary="Book an appointment for a customer")
async def book_appointment(
    body: dict,
    db: Client = Depends(get_db),
) -> dict:
    """Create a confirmed appointment in Firestore and upsert the customer record."""
    client_id = _resolve_client_id(body)
    customer_name = (body.get("customer_name") or "").strip()
    customer_phone = (body.get("customer_phone") or "").strip()
    service_name = (body.get("service_name") or "").strip()
    date_time_str = (body.get("date_time") or "").strip()

    if not all([customer_name, customer_phone, service_name, date_time_str]):
        raise HTTPException(
            status_code=400,
            detail="customer_name, customer_phone, service_name, and date_time are required.",
        )

    duration = int(body.get("duration_minutes") or 30)

    success = create_appointment(
        db=db,
        client_id=client_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        service_name=service_name,
        date_time=date_time_str,
        duration_minutes=duration,
    )

    if success:
        # Sync to Google Calendar only if the client has linked their account
        appointment_data = {
            "id": f"{client_id}_{customer_phone}_{date_time_str}",
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "service_name": service_name,
            "date_time": date_time_str,
            "duration_minutes": duration,
        }
        await create_calendar_event(db, client_id, appointment_data)

        result = {
            "success": True,
            "message": f"Appointment confirmed for {customer_name} on {date_time_str}.",
            "service": service_name,
        }
    else:
        result = {"success": False, "message": "Failed to book appointment. Please try again."}
    _log_tool_call("book-appointment", body, result)
    return result


# ─── SAVE CALL SUMMARY ───────────────────────────────────────────────────────

@router.post("/save-call-summary", summary="Save a call summary and log to Google Sheets")
async def save_call_summary(
    body: dict,
    db: Client = Depends(get_db),
) -> dict:
    """
    Persist a call log to Firestore and append a row to the Google Sheet.
    Called by the ElevenLabs agent at the end of each conversation.
    """
    client_id = _resolve_client_id(body)
    caller_phone = (body.get("caller_phone") or "").strip()
    summary = (body.get("summary") or "").strip()
    transcript = body.get("transcript") or ""
    duration_seconds = body.get("duration_seconds")
    customer_name = body.get("customer_name")

    if not caller_phone:
        raise HTTPException(status_code=400, detail="caller_phone is required.")

    saved = save_call_log(
        db=db,
        client_id=client_id,
        caller_phone=caller_phone,
        transcript=transcript,
        summary=summary,
        extracted_customer_name=customer_name or None,
    )

    # Look up the client's own sheet (falls back to global sheet if not linked)
    client_sheet_id: str | None = None
    try:
        client_doc = db.collection("clients").document(client_id).get()
        if client_doc.exists:
            client_sheet_id = (client_doc.to_dict() or {}).get("google_sheet_id")
    except Exception as exc:
        logger.warning("Could not fetch client sheet_id for %s: %s", client_id, exc)

    # Build a unique call ID for the Sheets row
    call_id = f"el_{client_id}_{caller_phone}_{str(uuid.uuid4())[:8]}"
    append_call_to_sheet(
        call_id=call_id,
        phone=caller_phone,
        summary=summary,
        sheet_id_override=client_sheet_id,
    )

    result = {
        "success": saved,
        "message": "Call summary saved." if saved else "Failed to save call summary.",
    }
    _log_tool_call("save-call-summary", body, result)
    return result
