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
from google.cloud.firestore import Client, FieldFilter

from app.auth.dependencies import require_admin
from app.auth.password import hash_password
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
    users = db.collection("users").where(filter=FieldFilter("client_id", "==", client_id)).limit(1).stream()
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
    existing = db.collection("users").where(filter=FieldFilter("username", "==", username)).limit(1).stream()
    if any(True for _ in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' already exists.",
        )

    now = datetime.now(tz=timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())

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


# ─── DELETE CLIENT ──────────────────────────────────────────────────────────

@router.delete(
    "/clients/{client_id}",
    summary="Permanently delete a client and all associated data",
    include_in_schema=False,
)
async def delete_client(
    client_id: str,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    """
    Permanently delete a client. Removes:
    - clients/{client_id}
    - users document linked via client_id
    - appointments, call_logs, customers documents for this client
    """
    client_ref = db.collection("clients").document(client_id)
    if not client_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    # Delete linked user document
    users = db.collection("users").where(filter=FieldFilter("client_id", "==", client_id)).stream()
    for user_doc in users:
        db.collection("users").document(user_doc.id).delete()
        logger.info("Deleted user %s for client %s", user_doc.id, client_id)

    # Delete appointments
    appointments = db.collection("appointments").where(filter=FieldFilter("client_id", "==", client_id)).stream()
    appt_count = 0
    for doc in appointments:
        doc.reference.delete()
        appt_count += 1

    # Delete call logs
    call_logs = db.collection("call_logs").where(filter=FieldFilter("client_id", "==", client_id)).stream()
    log_count = 0
    for doc in call_logs:
        doc.reference.delete()
        log_count += 1

    # Delete customers
    customers = db.collection("customers").where(filter=FieldFilter("client_id", "==", client_id)).stream()
    cust_count = 0
    for doc in customers:
        doc.reference.delete()
        cust_count += 1

    # Delete client document last
    client_ref.delete()

    logger.info(
        "Admin deleted client %s — appointments=%d, call_logs=%d, customers=%d",
        client_id, appt_count, log_count, cust_count,
    )
    return {
        "status": "deleted",
        "client_id": client_id,
        "deleted": {
            "appointments": appt_count,
            "call_logs": log_count,
            "customers": cust_count,
        },
    }


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


# ─── TOKEN USAGE ─────────────────────────────────────────────────────────────

@router.get(
    "/token-usage/{client_id}",
    summary="Get ElevenLabs token usage for a client",
    include_in_schema=False,
)
async def get_token_usage(
    client_id: str,
    start_date: str = None,
    end_date: str = None,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    from fastapi import Query as _Query
    from app.services.elevenlabs_service import get_agent_usage

    now_utc = datetime.now(tz=timezone.utc)
    if start_date is None:
        start_date = now_utc.replace(day=1).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = now_utc.strftime("%Y-%m-%d")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_unix = int(start_dt.timestamp())
    end_unix = int(end_dt.timestamp()) + 86399  # include full end day

    client_ref = db.collection("clients").document(client_id)
    client_doc = client_ref.get()
    if not client_doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    client_data = client_doc.to_dict()
    agent_id = client_data.get("elevenlabs_agent_id")
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client has no ElevenLabs agent configured.",
        )

    usage = await get_agent_usage(agent_id, start_unix, end_unix)

    price_per_character = client_data.get("price_per_character")
    currency = "USD"
    if price_per_character is None:
        pricing_doc = db.collection("pricing_config").document("global").get()
        if pricing_doc.exists:
            pricing_data = pricing_doc.to_dict()
            price_per_character = pricing_data.get("price_per_character", 0.0)
            currency = pricing_data.get("currency", "USD")
        else:
            price_per_character = 0.0

    total_characters = usage.get("total_characters", 0)
    estimated_cost = total_characters * price_per_character

    return {
        "client_id": client_id,
        "agent_id": agent_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_characters": total_characters,
        "conversation_count": usage.get("conversation_count", 0),
        "total_duration_secs": usage.get("total_duration_secs", 0),
        "price_per_character": price_per_character,
        "currency": currency,
        "estimated_cost": estimated_cost,
        "conversations": usage.get("conversations", []),
    }


# ─── PRICING — GET ───────────────────────────────────────────────────────────

@router.get(
    "/pricing",
    summary="Get global pricing config and per-client overrides",
    include_in_schema=False,
)
async def get_pricing(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    pricing_doc = db.collection("pricing_config").document("global").get()
    if pricing_doc.exists:
        global_data = pricing_doc.to_dict()
        global_pricing = {
            "price_per_character": global_data.get("price_per_character", 0.0),
            "currency": global_data.get("currency", "USD"),
            "updated_at": global_data.get("updated_at"),
        }
    else:
        global_pricing = {"price_per_character": 0.0, "currency": "USD", "updated_at": None}

    client_overrides = []
    for doc in db.collection("clients").stream():
        data = doc.to_dict()
        ppc = data.get("price_per_character")
        if ppc is not None:
            client_overrides.append({
                "client_id": doc.id,
                "business_name": data.get("business_name", ""),
                "price_per_character": ppc,
            })

    return {"global": global_pricing, "client_overrides": client_overrides}


# ─── PRICING — PUT ───────────────────────────────────────────────────────────

@router.put(
    "/pricing",
    summary="Update global pricing config",
    include_in_schema=False,
)
async def update_pricing(
    body: dict,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    price_per_character = body.get("price_per_character")
    if price_per_character is None or price_per_character < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'price_per_character' must be a non-negative number.",
        )

    currency = body.get("currency", "USD")
    apply_to_all = body.get("apply_to_all", False)

    now = datetime.now(tz=timezone.utc).isoformat()
    db.collection("pricing_config").document("global").set({
        "price_per_character": price_per_character,
        "currency": currency,
        "updated_at": now,
    })

    if apply_to_all:
        for doc in db.collection("clients").stream():
            db.collection("clients").document(doc.id).set(
                {"price_per_character": None}, merge=True
            )

    return {"status": "updated", "applied_to_all": apply_to_all}


# ─── PER-CLIENT PRICING ──────────────────────────────────────────────────────

@router.patch(
    "/clients/{client_id}/pricing",
    summary="Set or clear per-client price override",
    include_in_schema=False,
)
async def update_client_pricing(
    client_id: str,
    body: dict,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    client_ref = db.collection("clients").document(client_id)
    if not client_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    price_per_character = body.get("price_per_character")
    client_ref.set({"price_per_character": price_per_character}, merge=True)

    return {"status": "updated", "client_id": client_id, "price_per_character": price_per_character}


# ─── ELEVENLABS AGENTS — LIST ────────────────────────────────────────────────

@router.get(
    "/elevenlabs/agents",
    summary="List ElevenLabs agents",
    include_in_schema=False,
)
async def list_elevenlabs_agents(
    search: str = None,
    cursor: str = None,
    page_size: int = 30,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    from app.services.elevenlabs_service import list_agents

    result = await list_agents(search, cursor, page_size)
    return result


# ─── ELEVENLABS AGENTS — GET ─────────────────────────────────────────────────

@router.get(
    "/elevenlabs/agents/{agent_id}",
    summary="Get a single ElevenLabs agent",
    include_in_schema=False,
)
async def get_elevenlabs_agent(
    agent_id: str,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    from app.services.elevenlabs_service import get_agent

    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    conv_config = agent.get("conversation_config", {})
    agent_section = conv_config.get("agent", {})
    prompt_section = agent_section.get("prompt", {})

    return {
        "agent_id": agent.get("agent_id", agent_id),
        "name": agent.get("name", ""),
        "prompt": prompt_section.get("prompt", ""),
        "first_message": agent_section.get("first_message", ""),
    }


# ─── ELEVENLABS AGENTS — DUPLICATE ───────────────────────────────────────────

@router.post(
    "/elevenlabs/agents/duplicate",
    summary="Duplicate an ElevenLabs agent",
    include_in_schema=False,
)
async def duplicate_elevenlabs_agent(
    body: dict,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db),
) -> dict:
    from app.services.elevenlabs_service import duplicate_agent, update_agent_system_prompt

    source_agent_id = body.get("source_agent_id")
    if not source_agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'source_agent_id' is required.",
        )

    name = body.get("name")
    prompt = body.get("prompt")

    new_agent_id = await duplicate_agent(source_agent_id, name)
    if not new_agent_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ElevenLabs agent duplication failed.")

    if prompt:
        await update_agent_system_prompt(new_agent_id, prompt)

    return {"status": "created", "new_agent_id": new_agent_id, "name": name}
