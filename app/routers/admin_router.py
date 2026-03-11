"""
admin_router.py — Hidden admin panel under /automiteui/mngr-sys-access-78/*.

All routes:
  - Require admin:all scope JWT
  - Are excluded from OpenAPI docs (include_in_schema=False)
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client

from app.auth.dependencies import require_admin
from app.auth.password import hash_password
from app.config import settings
from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/mngr-sys-access-78",
    tags=["Admin"],
)


# ─── DASHBOARD OVERVIEW ─────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Admin dashboard overview",
    include_in_schema=False,
)
async def admin_dashboard(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """System overview: total clients, active/inactive counts, recent activity."""
    clients_docs = db.collection("clients").stream()
    clients = [doc.to_dict() for doc in clients_docs]

    total = len(clients)
    active = sum(1 for c in clients if c.get("is_active", True))
    inactive = total - active

    # Count recent call logs (last 24h would need a date filter, so just total)
    call_logs_count = len(list(db.collection("call_logs").limit(100).stream()))
    appointments_count = len(list(db.collection("appointments").limit(100).stream()))

    return {
        "total_clients": total,
        "active_clients": active,
        "inactive_clients": inactive,
        "total_call_logs": call_logs_count,
        "total_appointments": appointments_count,
    }


# ─── LIST ALL CLIENTS ───────────────────────────────────────────────────────

@router.get(
    "/clients",
    summary="List all registered clients",
    include_in_schema=False,
)
async def list_clients(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch all client records with their current status."""
    docs = db.collection("clients").stream()
    clients = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        clients.append(data)

    clients.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"total": len(clients), "clients": clients}


# ─── TOGGLE CLIENT STATUS ───────────────────────────────────────────────────

@router.patch(
    "/clients/{client_id}/status",
    summary="Activate or deactivate a client",
    include_in_schema=False,
)
async def toggle_client_status(
    client_id: str,
    body: dict,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """
    Toggle a client's active/inactive status.
    Body: { "is_active": true/false }
    Also syncs the change to their Vapi assistant.
    """
    is_active = body.get("is_active")
    if is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'is_active' field (bool) is required.",
        )

    doc_ref = db.collection("clients").document(client_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    now = datetime.now(tz=timezone.utc).isoformat()
    doc_ref.set({"is_active": is_active, "updated_at": now}, merge=True)

    # Sync to Vapi
    client_data = doc.to_dict()
    vapi_id = client_data.get("vapi_assistant_id")
    if vapi_id and settings.vapi_api_key:
        try:
            from app.services.vapi_service import toggle_assistant
            await toggle_assistant(vapi_id, is_active)
        except Exception as exc:
            logger.warning("Vapi toggle sync failed: %s", exc)

    action = "activated" if is_active else "deactivated"
    logger.info("Client %s %s by admin", client_id, action)
    return {"status": action, "client_id": client_id}


# ─── UPDATE SUBSCRIPTION ────────────────────────────────────────────────────

@router.patch(
    "/clients/{client_id}/subscription",
    summary="Change a client's subscription tier",
    include_in_schema=False,
)
async def update_subscription(
    client_id: str,
    body: dict,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """
    Update subscription status for a client.
    Body: { "subscription_status": "standard" | "pro" | "enterprise" | "cancelled" }
    """
    new_status = body.get("subscription_status")
    valid_statuses = {"standard", "pro", "enterprise", "cancelled", "active"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    doc_ref = db.collection("clients").document(client_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    now = datetime.now(tz=timezone.utc).isoformat()
    doc_ref.set({"subscription_status": new_status, "updated_at": now}, merge=True)

    # Also update the linked user document
    users = db.collection("users").where("client_id", "==", client_id).limit(1).stream()
    for user_doc in users:
        db.collection("users").document(user_doc.id).set(
            {"subscription_status": new_status, "updated_at": now}, merge=True
        )

    logger.info("Client %s subscription changed to '%s'", client_id, new_status)
    return {"status": "updated", "client_id": client_id, "subscription_status": new_status}


# ─── MANUAL CLIENT ADDITION ─────────────────────────────────────────────────

@router.post(
    "/clients",
    summary="Manually add a VIP or corporate client",
    include_in_schema=False,
    status_code=status.HTTP_201_CREATED,
)
async def add_client_manually(
    body: dict,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """
    Manually register a client (VIP/corporate).
    Body: { "username": "...", "password": "...", "client_name": "...", "assistant_name": "..." }
    """
    username = body.get("username")
    password = body.get("password")
    client_name = body.get("client_name")
    assistant_name = body.get("assistant_name", client_name)

    if not all([username, password, client_name]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username, password, and client_name are required.",
        )

    # Check for duplicate username
    existing = db.collection("users").where("username", "==", username).limit(1).stream()
    if any(True for _ in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' already exists.",
        )

    now = datetime.now(tz=timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())

    # Try to clone Vapi assistant
    vapi_assistant_id = None
    if settings.vapi_api_key:
        try:
            from app.services.vapi_service import clone_assistant
            vapi_assistant_id = await clone_assistant(
                client_name=client_name, assistant_name=assistant_name
            )
            if vapi_assistant_id:
                client_id = vapi_assistant_id
        except Exception as exc:
            logger.warning("Vapi clone failed for manual add: %s", exc)

    # Create user
    user_doc = {
        "id": user_id,
        "username": username,
        "hashed_password": hash_password(password),
        "is_admin": False,
        "subscription_status": "active",
        "client_id": client_id,
        "client_name": client_name,
        "assistant_name": assistant_name,
        "created_at": now,
        "added_by": "admin",
    }
    db.collection("users").document(user_id).set(user_doc)

    # Create client
    client_doc = {
        "id": client_id,
        "user_id": user_id,
        "business_name": client_name,
        "assistant_name": assistant_name,
        "vapi_assistant_id": vapi_assistant_id,
        "services": [],
        "operating_hours": {},
        "policies": {},
        "currency": "INR",
        "is_active": True,
        "subscription_status": "active",
        "created_at": now,
    }
    db.collection("clients").document(client_id).set(client_doc)

    logger.info("Admin manually added client '%s' (user=%s, client=%s)", client_name, user_id, client_id)
    return {"status": "created", "user_id": user_id, "client_id": client_id, "username": username}


# ─── REFRESH TOOL TOKENS ────────────────────────────────────────────────────

@router.post(
    "/refresh-tool-tokens",
    summary="Regenerate all M2M tool-level tokens",
    include_in_schema=False,
)
async def refresh_tool_tokens(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """
    Rotate all machine-to-machine tokens used for external API communication.
    This is a security hygiene operation for rotating keys across integrated AI APIs.
    """
    from app.auth.jwt_handler import create_access_token

    now = datetime.now(tz=timezone.utc).isoformat()

    # Regenerate tool-scope tokens for all active clients
    clients = db.collection("clients").stream()
    rotated_count = 0

    for doc in clients:
        client_data = doc.to_dict()
        if not client_data.get("is_active", True):
            continue

        token_data = {
            "sub": doc.id,
            "scope": "tool",
            "client_id": doc.id,
        }
        new_token = create_access_token(token_data, scope="tool")

        # Store the new token reference
        token_id = str(uuid.uuid4())
        db.collection("tokens").document(token_id).set({
            "id": token_id,
            "client_id": doc.id,
            "tool_scope": "tool",
            "token_hash": new_token[:16] + "...",  # Store partial for audit
            "created_at": now,
            "is_revoked": False,
        })
        rotated_count += 1

    logger.info("Admin rotated tool tokens for %d clients", rotated_count)
    return {"status": "rotated", "clients_affected": rotated_count}
