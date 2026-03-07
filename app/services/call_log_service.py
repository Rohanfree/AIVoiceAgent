"""
call_log_service.py - Persist Vapi call-end data to Firestore.

Saves a structured call log that includes:
  - The actual caller phone (original number if call was forwarded)
  - The number that forwarded the call (if applicable)
  - Call metadata: Vapi call ID, ended reason, duration, transcript, summary
"""

import logging
import uuid
from datetime import datetime, timezone

from google.cloud.firestore import Client

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def save_vapi_call_log(
    db: Client,
    client_id: str,
    caller_phone: str,
    forwarded_from: str | None,
    vapi_call_id: str | None,
    ended_reason: str | None,
    duration_seconds: float | None,
    transcript: str | None,
    summary: str | None,
) -> bool:
    """
    Persist a Vapi call-end log document to Firestore.

    Args:
        db:               Firestore client.
        client_id:        Business client identifier (from app config).
        caller_phone:     The direct caller's phone number (Number 2 if forwarded,
                          or Number 1 if called directly).
        forwarded_from:   The ORIGINAL caller (Number 1) when call was forwarded.
                          None if the call was dialled directly.
        vapi_call_id:     Vapi's unique call ID for traceability.
        ended_reason:     Why the call ended (e.g. 'customer-ended-call').
        duration_seconds: Total call length in seconds.
        transcript:       Full conversation transcript.
        summary:          Auto-generated call summary.

    Returns:
        True on success, False on any error.
    """
    try:
        now = _utcnow_iso()
        log_id = str(uuid.uuid4())

        # The "true" caller is the forwarded-from number when available,
        # otherwise it's the direct caller.
        true_caller = forwarded_from or caller_phone

        log_doc = {
            "id": log_id,
            "client_id": client_id,
            # The original caller - this is what you care about
            "true_caller_phone": true_caller,
            # Raw numbers for full audit trail
            "direct_caller_phone": caller_phone,
            "forwarded_from_phone": forwarded_from,
            # Call metadata
            "vapi_call_id": vapi_call_id,
            "ended_reason": ended_reason,
            "duration_seconds": duration_seconds,
            "transcript": transcript,
            "summary": summary,
            "created_at": now,
        }

        db.collection("call_logs").document(log_id).set(log_doc)
        logger.info(
            "Vapi call log %s saved | client=%s | true_caller=%s | forwarded_from=%s",
            log_id,
            client_id,
            true_caller,
            forwarded_from,
        )
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save Vapi call log: %s", exc, exc_info=True)
        return False
