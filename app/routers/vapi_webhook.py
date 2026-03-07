"""
vapi_webhook.py - Handles incoming webhook events from Vapi.

Currently handles:
  POST /vapi/call-ended  →  Triggered by Vapi when a call finishes.
                             Saves call details + caller identification to Firestore.

Configure this URL in your Vapi dashboard under:
  Assistant → Server URL → https://automite.rohanthomas.dpdns.org/vapi/call-ended
"""

import logging

from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.config import settings
from app.db import get_db
from app.schemas.vapi_models import VapiCallEndedPayload
from app.services.call_log_service import save_vapi_call_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vapi",
    tags=["Vapi Webhooks"],
)


@router.post(
    "/call-ended",
    summary="Vapi call-ended webhook",
    description=(
        "Receives end-of-call-report events from Vapi. "
        "Saves caller details, forwarded-from number (if applicable), "
        "transcript, summary, and call metadata to Firestore."
    ),
)
async def vapi_call_ended(
    payload: VapiCallEndedPayload,
    db: Client = Depends(get_db),
) -> dict:
    """
    Handle Vapi's 'end-of-call-report' webhook.

    Vapi posts this when a call ends. We extract:
      - caller_phone : the number that directly rang the Vapi line
      - forwarded_from : the ORIGINAL caller when call was forwarded
        (e.g. Number1 → forwards → VapiNumber → caller_phone is the forwarder,
                                                  forwarded_from is Number1)

    All data is saved to Firestore `call_logs` collection.
    Returns {"status": "received"} so Vapi knows we got it.
    """
    msg = payload.message

    # Ignore non-call-ended events (Vapi may send other webhook types)
    if not msg or msg.type != "end-of-call-report":
        logger.debug("Ignoring non-call-ended Vapi webhook: type=%s", msg.type if msg else "null")
        return {"status": "ignored", "reason": "not an end-of-call-report event"}

    call = msg.call

    # ── Resolve client_id from assistantId (multi-tenant SaaS) ──────────────
    # Each client has their own Vapi assistant; its ID is the tenant identifier.
    # Falls back to configured default only when assistantId is absent.
    client_id: str = settings.client_id
    if call and hasattr(call, "assistant_id") and call.assistant_id:
        client_id = call.assistant_id
    logger.debug("call-ended: client_id resolved to %s", client_id)

    # Extract phone numbers from the call object
    caller_phone: str = ""
    forwarded_from: str | None = None

    if call and call.customer:
        caller_phone = call.customer.number or ""
        forwarded_from = call.customer.number_forwarded_from or None

    if forwarded_from:
        logger.info(
            "Forwarded call received | original_caller=%s | forwarded_via=%s | client=%s",
            forwarded_from,
            caller_phone,
            client_id,
        )
    else:
        logger.info("Direct call received | caller=%s | client=%s", caller_phone, client_id)

    # Persist to Firestore
    save_vapi_call_log(
        db=db,
        client_id=client_id,
        caller_phone=caller_phone,
        forwarded_from=forwarded_from,
        vapi_call_id=call.id if call else None,
        ended_reason=call.ended_reason if call else None,
        duration_seconds=call.duration_seconds if call else None,
        transcript=msg.transcript,
        summary=msg.summary,
    )

    return {"status": "received"}
