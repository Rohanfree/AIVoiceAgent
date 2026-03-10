"""
agent_tools.py - APIRouter for all /agent-tools endpoints.

Each endpoint now accepts Vapi's tool-call webhook format:
  POST body: { "message": { "type": "tool-calls", "call": { "assistantId": "..." },
                             "toolCallList": [{ "id": "...", "function": { "name": "...", "arguments": {...} } }] } }

The assistantId is extracted and used as client_id (each client gets their own Vapi assistant).
Function arguments are extracted from toolCallList[0].function.arguments.
Responses are returned in Vapi's expected format:
  { "results": [{ "toolCallId": "...", "result": <your JSON> }] }

For backward-compat / direct testing, a plain JSON body (without the Vapi wrapper) still works —
client_id falls back to settings.client_id in that case.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.cloud.firestore import Client

from app.config import settings
from app.db import get_db
from app.schemas.vapi_models import VapiToolCallPayload
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
from app.services.customer_service import get_customer_by_phone, get_last_call_summary, upsert_customer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent-tools",
    tags=["Agent Tools"],
)


# ─── Vapi payload helpers ──────────────────────────────────────────────────────

def _extract_vapi_context(payload: VapiToolCallPayload) -> tuple[str, str | None, dict]:
    """
    Pull client_id, tool_call_id, and function arguments from a Vapi tool-call payload.

    Returns:
        (client_id, tool_call_id, arguments)
        - client_id    : assistantId from the call metadata, or settings default
        - tool_call_id : must be echoed in the Vapi response
        - arguments    : the AI-extracted function params dict
    """
    client_id = settings.client_id
    tool_call_id: str | None = None
    arguments: dict = {}

    msg = payload.message
    if msg:
        # Extract assistantId → use as client_id
        if msg.call and msg.call.assistant_id:
            client_id = msg.call.assistant_id
            logger.debug("client_id resolved from assistantId: %s", client_id)

        # Extract arguments + toolCallId from first item in toolCallList
        if msg.tool_call_list:
            first = msg.tool_call_list[0]
            tool_call_id = first.id
            if first.function and first.function.arguments:
                arguments = first.function.arguments

    return client_id, tool_call_id, arguments


def _vapi_response(tool_call_id: str | None, result: Any) -> dict:
    """
    Wrap a result dict in Vapi's expected tool-call response format.
    If no tool_call_id exists (direct call), just return the result.
    """
    if tool_call_id:
        return {"results": [{"toolCallId": tool_call_id, "result": result}]}
    return result


# ─── Debug helpers ─────────────────────────────────────────────────────────────

def _log_debug(tag: str, data: Any) -> None:
    if settings.debug:
        payload = data.model_dump() if hasattr(data, "model_dump") else data
        logger.debug("[%s]\n%s", tag, json.dumps(payload, indent=2, default=str))


# ─── A) GET CLIENT BY MOBILE ──────────────────────────────────────────────────

@router.post(
    "/get-client-by-mobile",
    summary="Look up a customer by phone number",
    description=(
        "Accepts a Vapi tool-call webhook. Reads assistantId as client_id. "
        "Searches for the customer by phone and returns their details."
    ),
)
async def get_client_by_mobile(
    request: Request,
    db: Client = Depends(get_db),
) -> dict:
    body = await request.json()
    _log_debug("REQUEST /get-client-by-mobile", body)

    payload = VapiToolCallPayload.model_validate(body)
    client_id, tool_call_id, args = _extract_vapi_context(payload)

    customer_phone: str = args.get("customer_phone", "")
    if not customer_phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="customer_phone is required",
        )

    customer = get_customer_by_phone(db=db, client_id=client_id, phone=customer_phone)

    if customer:
        last_summary = get_last_call_summary(
            db=db, client_id=client_id, phone=customer_phone
        )
        result = {
            "found": True,
            "customer_name": customer.get("name", ""),
            "last_visit": customer.get("last_visit"),
            "notes": customer.get("notes"),
            "last_call_summary": last_summary,
        }
    else:
        result = {"found": False}

    resp = _vapi_response(tool_call_id, result)
    _log_debug("RESPONSE /get-client-by-mobile", resp)
    return resp


# ─── B) GET SERVICES AND PRICES ───────────────────────────────────────────────

@router.post(
    "/get-services-and-prices",
    summary="Retrieve services and pricing for a client",
    description="Accepts a Vapi tool-call webhook. Reads assistantId as client_id.",
)
async def get_services_and_prices(
    request: Request,
    db: Client = Depends(get_db),
) -> dict:
    body = await request.json()
    _log_debug("REQUEST /get-services-and-prices", body)

    payload = VapiToolCallPayload.model_validate(body)
    client_id, tool_call_id, _ = _extract_vapi_context(payload)

    client_doc = get_client_services(db=db, client_id=client_id)
    if client_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found.",
        )

    result = {
        "business_name": client_doc.get("business_name"),
        "currency": client_doc.get("currency", "INR"),
        "operating_hours": client_doc.get("operating_hours", {}),
        "policies": client_doc.get("policies", {}),
        "services": [
            {
                "name": svc.get("name", ""),
                "category": svc.get("category", ""),
                "duration": int(svc.get("duration", 0)),
                "price": float(svc.get("price", 0.0)),
                "description": svc.get("description", ""),
            }
            for svc in client_doc.get("services", [])
        ],
    }

    resp = _vapi_response(tool_call_id, result)
    _log_debug("RESPONSE /get-services-and-prices", resp)
    return resp


# ─── C) CHECK AVAILABILITY ────────────────────────────────────────────────────

@router.post(
    "/check-availability",
    summary="Check whether an appointment slot is free",
    description="Accepts a Vapi tool-call webhook. Reads assistantId as client_id.",
)
async def check_availability(
    request: Request,
    db: Client = Depends(get_db),
) -> dict:
    body = await request.json()
    _log_debug("REQUEST /check-availability", body)

    payload = VapiToolCallPayload.model_validate(body)
    client_id, tool_call_id, args = _extract_vapi_context(payload)

    service_name: str = args.get("service_name", "")
    date_time_str: str = args.get("date_time", "")

    if not service_name or not date_time_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="service_name and date_time are required",
        )

    duration = get_service_duration(db=db, client_id=client_id, service_name=service_name)
    if duration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_name}' not found for client '{client_id}'.",
        )

    try:
        requested_dt = datetime.fromisoformat(date_time_str)
        if requested_dt.tzinfo is None:
            requested_dt = requested_dt.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date_time format: {exc}",
        ) from exc

    is_available, next_available = check_slot_availability(
        db=db,
        client_id=client_id,
        service_name=service_name,
        requested_dt=requested_dt,
        duration_minutes=duration,
    )

    if is_available:
        result = {"available": True}
    else:
        result = {"available": False, "next_available": next_available or ""}

    resp = _vapi_response(tool_call_id, result)
    _log_debug("RESPONSE /check-availability", resp)
    return resp


# ─── D) BOOK APPOINTMENT ──────────────────────────────────────────────────────

@router.post(
    "/book-appointment",
    summary="Book an appointment for a customer",
    description="Accepts a Vapi tool-call webhook. Reads assistantId as client_id.",
)
async def book_appointment(
    request: Request,
    db: Client = Depends(get_db),
) -> dict:
    body = await request.json()
    _log_debug("REQUEST /book-appointment", body)

    payload = VapiToolCallPayload.model_validate(body)
    client_id, tool_call_id, args = _extract_vapi_context(payload)

    customer_name: str = args.get("customer_name", "")
    customer_phone: str = args.get("customer_phone", "")
    service_name: str = args.get("service_name", "")
    date_time_str: str = args.get("date_time", "")

    if not all([customer_name, customer_phone, service_name, date_time_str]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="customer_name, customer_phone, service_name, and date_time are all required",
        )

    client_doc = get_client_services(db=db, client_id=client_id)
    if client_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found.",
        )

    services = client_doc.get("services", [])
    service = find_service(services, service_name)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_name}' not found for client '{client_id}'.",
        )

    success = create_appointment(
        db=db,
        client_id=client_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        service_name=service_name,
        date_time=date_time_str,
        duration_minutes=int(service.get("duration", 0)),
    )

    result = {"status": "confirmed" if success else "failed"}
    resp = _vapi_response(tool_call_id, result)
    _log_debug("RESPONSE /book-appointment", resp)
    return resp


# ─── E) SAVE CALL LOG (legacy / direct use) ───────────────────────────────────

@router.post(
    "/save-call-log",
    summary="Persist a call log after the call ends",
    description=(
        "Legacy endpoint for saving call logs directly. "
        "For Vapi, use the /vapi/call-ended webhook instead."
    ),
)
async def save_call_log_endpoint(
    request: Request,
    db: Client = Depends(get_db),
) -> dict:
    body = await request.json()
    _log_debug("REQUEST /save-call-log", body)

    payload = VapiToolCallPayload.model_validate(body)
    client_id, tool_call_id, args = _extract_vapi_context(payload)

    caller_phone: str = args.get("caller_phone", "")
    transcript: str = args.get("transcript", "")
    summary: str = args.get("summary", "")
    extracted_customer_name: str | None = args.get("extracted_customer_name")

    if not caller_phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="caller_phone is required",
        )

    success = save_call_log(
        db=db,
        client_id=client_id,
        caller_phone=caller_phone,
        transcript=transcript,
        summary=summary,
        extracted_customer_name=extracted_customer_name,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save call log.",
        )

    result = {"status": "saved"}
    resp = _vapi_response(tool_call_id, result)
    _log_debug("RESPONSE /save-call-log", resp)
    return resp
