"""
customer_service.py - CRUD helpers for the 'customers' Firestore collection.

Responsibilities:
- Fetching a customer by (client_id, phone)
- Upserting a customer record (create or update)
"""

import logging
from datetime import datetime, timezone

from google.cloud.firestore import Client

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """Helper: return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def get_customer_by_phone(
    db: Client, client_id: str, phone: str
) -> dict | None:
    """
    Look up a customer in Firestore by client_id + phone number.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        phone: Customer phone number to search.

    Returns:
        Customer document dict, or None if not found.
    """
    docs = (
        db.collection("customers")
        .where("client_id", "==", client_id)
        .where("phone", "==", phone)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        logger.debug("Found customer: %s", data)
        return data
    logger.debug("No customer found for client=%s phone=%s", client_id, phone)
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
    Create a new customer or update an existing one.

    - If the customer already exists (matched by client_id + phone), patch the
      provided fields and refresh updated_at.
    - If no record exists, create a fresh document with all base fields.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        phone: Customer phone number (used as lookup key).
        name: Optional customer full name.
        notes: Optional freeform notes.
        last_visit: Optional ISO date string of the most recent visit.
    """
    now = _utcnow_iso()

    existing = get_customer_by_phone(db, client_id, phone)

    if existing:
        # Build a partial update dict with only provided fields
        update_data: dict = {"updated_at": now}
        if name is not None:
            update_data["name"] = name
        if notes is not None:
            update_data["notes"] = notes
        if last_visit is not None:
            update_data["last_visit"] = last_visit

        db.collection("customers").document(existing["id"]).update(update_data)
        logger.debug("Updated customer %s: %s", existing["id"], update_data)
    else:
        # Create a new customer document
        new_doc = {
            "client_id": client_id,
            "phone": phone,
            "name": name or "",
            "last_visit": last_visit,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        }
        ref = db.collection("customers").document()
        ref.set(new_doc)
        logger.debug("Created new customer %s: %s", ref.id, new_doc)
