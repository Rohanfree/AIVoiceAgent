"""
customer_service.py - CRUD helpers for the 'customers' Firestore collection.

Responsibilities:
- Fetching a customer by (client_id, phone) via a fast point read
- Fetching the most recent call log summary for a customer
- Upserting a customer record (create or update) using a deterministic doc ID

Document ID strategy: {client_id}_{phone}
"""

import logging
from datetime import datetime, timezone

from google.cloud.firestore import Client

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """Helper: return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _customer_doc_id(client_id: str, phone: str) -> str:
    """Build a deterministic Firestore document ID for a customer."""
    return f"{client_id}_{phone}"


def get_customer_by_phone(
    db: Client, client_id: str, phone: str
) -> dict | None:
    """
    Look up a customer in Firestore by client_id + phone number.

    Uses a direct point read (no query) via a deterministic document ID.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        phone: Customer phone number.

    Returns:
        Customer document dict (with 'id' key), or None if not found.
    """
    doc_id = _customer_doc_id(client_id, phone)
    doc = db.collection("customers").document(doc_id).get()

    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        logger.debug("Found customer: %s", data)
        return data

    logger.debug("No customer found for client=%s phone=%s", client_id, phone)
    return None


def get_last_call_summary(
    db: Client, client_id: str, phone: str
) -> str | None:
    """
    Fetch the summary from the most recent call log for this customer.

    Queries the 'call_logs' collection filtered by client_id and
    true_caller_phone, ordered by created_at descending, limited to 1.

    Requires a Firestore composite index on:
        (client_id ASC, true_caller_phone ASC, created_at DESC)

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        phone: Customer phone number (matched against true_caller_phone).

    Returns:
        The summary string from the latest call, or None if no logs exist
        or the composite index has not been created yet.
    """
    try:
        from google.cloud.firestore import FieldFilter
        docs = (
            db.collection("call_logs")
            .where(filter=FieldFilter("client_id", "==", client_id))
            .where(filter=FieldFilter("true_caller_phone", "==", phone))
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            summary = data.get("summary")
            logger.debug(
                "Last call summary for client=%s phone=%s: %s",
                client_id, phone, summary
            )
            return summary

        logger.debug("No call logs found for client=%s phone=%s", client_id, phone)
        return None

    except Exception as exc:
        # Gracefully handle missing composite index — endpoint still works
        # without the summary. Create the index at the URL printed below.
        logger.warning(
            "get_last_call_summary failed (composite index may be missing): %s", exc
        )
        return None




def upsert_customer(
    db: Client,
    client_id: str,
    phone: str,
    name: str | None = None,
    notes: str | None = None,
    last_visit: str | None = None,
) -> None:
    """
    Create a new customer or update an existing one using a deterministic ID.

    Uses Firestore's merge=True set() so no pre-read is needed.
    Sets created_at only when the document does not yet exist.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        phone: Customer phone number (used as part of document ID).
        name: Optional customer full name.
        notes: Optional freeform notes.
        last_visit: Optional ISO date string of the most recent visit.
    """
    now = _utcnow_iso()
    doc_id = _customer_doc_id(client_id, phone)

    # Check existence with a point read to decide whether to set created_at
    doc_ref = db.collection("customers").document(doc_id)
    existing = doc_ref.get()

    data: dict = {
        "client_id": client_id,
        "phone": phone,
        "updated_at": now,
    }

    if not existing.exists:
        data["created_at"] = now

    if name is not None:
        data["name"] = name
    if notes is not None:
        data["notes"] = notes
    if last_visit is not None:
        data["last_visit"] = last_visit

    doc_ref.set(data, merge=True)
    logger.debug(
        "%s customer %s: %s",
        "Updated" if existing.exists else "Created",
        doc_id,
        data,
    )
