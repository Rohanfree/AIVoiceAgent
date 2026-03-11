"""
client_router.py — Client portal endpoints under /automiteui/client-portal/*.

Authenticated routes for clients to manage their profile, view appointments,
and access call logs. All routes require a 'dashboard' scope JWT.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client

from app.auth.dependencies import get_current_user
from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/client-portal",
    tags=["Client Portal"],
)


# ─── GET PROFILE ────────────────────────────────────────────────────────────

@router.get(
    "/profile",
    summary="Get current client's profile",
)
async def get_profile(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch the authenticated client's full profile from Firestore."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No client profile associated with this account.",
        )

    doc = db.collection("clients").document(client_id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found.",
        )

    data = doc.to_dict()
    # Remove sensitive fields
    data.pop("vapi_assistant_id", None)
    return data


# ─── UPDATE PROFILE ─────────────────────────────────────────────────────────

@router.put(
    "/profile",
    summary="Update client's services, timings, and business info",
)
async def update_profile(
    updates: dict,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """
    Update the client's profile. Accepted fields:
    - business_name, services, operating_hours, policies, currency
    """
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No client profile associated with this account.",
        )

    allowed_fields = {"business_name", "services", "operating_hours", "policies", "currency"}
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}

    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid fields to update. Allowed: {allowed_fields}",
        )

    from datetime import datetime, timezone
    filtered["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

    db.collection("clients").document(client_id).set(filtered, merge=True)
    logger.info("Client %s profile updated: %s", client_id, list(filtered.keys()))

    # Sync to Vapi if configured
    doc = db.collection("clients").document(client_id).get()
    if doc.exists:
        client_data = doc.to_dict()
        vapi_id = client_data.get("vapi_assistant_id")
        if vapi_id:
            try:
                from app.services.vapi_service import update_assistant
                await update_assistant(vapi_id, {
                    "name": client_data.get("assistant_name", ""),
                    "metadata": {"business_name": client_data.get("business_name", "")},
                })
            except Exception as exc:
                logger.warning("Vapi sync failed (non-blocking): %s", exc)

    return {"status": "updated", "fields": list(filtered.keys())}


# ─── LIST APPOINTMENTS ───────────────────────────────────────────────────────

@router.get(
    "/appointments",
    summary="List appointments for the current client",
)
async def list_appointments(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch all appointments for the authenticated client."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No client profile.")

    docs = db.collection("appointments").where("client_id", "==", client_id).stream()
    appointments = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        appointments.append(data)

    # Sort by date_time descending
    appointments.sort(key=lambda x: x.get("date_time", ""), reverse=True)

    return {"client_id": client_id, "total": len(appointments), "appointments": appointments}


# ─── LIST CALL LOGS ──────────────────────────────────────────────────────────

@router.get(
    "/call-logs",
    summary="List call logs for the current client",
)
async def list_call_logs(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch all call logs for the authenticated client."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No client profile.")

    docs = db.collection("call_logs").where("client_id", "==", client_id).stream()
    logs = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        logs.append(data)

    # Sort by created_at descending
    logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"client_id": client_id, "total": len(logs), "call_logs": logs}
