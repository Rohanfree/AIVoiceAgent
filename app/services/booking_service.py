"""
booking_service.py - Handles appointment creation and validation.

Responsibilities:
- Validate that the requested service exists for the client
- Persist a new appointment to Firestore
- Trigger customer upsert after successful booking
"""

import logging
import uuid
from datetime import datetime, timezone

from google.cloud.firestore import Client

from app.services.customer_service import upsert_customer

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """Helper: return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def get_client_services(db: Client, client_id: str) -> dict | None:
    """
    Fetch the full client document for a given client_id.

    Returns:
        The client document dict (contains services, operating_hours, policies etc.),
        or None if the client document does not exist.
    """
    client_doc = db.collection("clients").document(client_id).get()
    if not client_doc.exists:
        logger.warning("Client not found when fetching services: %s", client_id)
        return None
    return client_doc.to_dict()


def find_service(services: list[dict], service_name: str) -> dict | None:
    """
    Case-insensitive lookup of a service by name within a services list.

    Args:
        services: List of service dicts (name, duration, price).
        service_name: The service name to look for.

    Returns:
        The matching service dict, or None if not found.
    """
    for svc in services:
        if svc.get("name", "").lower() == service_name.lower():
            return svc
    return None


def create_appointment(
    db: Client,
    client_id: str,
    customer_name: str,
    customer_phone: str,
    service_name: str,
    date_time: str,
    duration_minutes: int,
) -> bool:
    """
    Persist a new appointment document to Firestore and upsert the customer.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        customer_name: Full name of the customer.
        customer_phone: Phone number of the customer.
        service_name: Name of the booked service.
        date_time: ISO 8601 string for appointment start.
        duration_minutes: Duration of the service in minutes.

    Returns:
        True on success, False if any exception occurs.
    """
    try:
        now = _utcnow_iso()
        appt_id = str(uuid.uuid4())

        appointment_doc = {
            "id": appt_id,
            "client_id": client_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "service_name": service_name,
            "date_time": date_time,
            "duration_minutes": duration_minutes,  # stored so availability checks work
            "status": "confirmed",
            "created_at": now,
        }

        db.collection("appointments").document(appt_id).set(appointment_doc)
        logger.info("Appointment %s created for client %s", appt_id, client_id)

        # Upsert customer record with latest visit date
        upsert_customer(
            db=db,
            client_id=client_id,
            phone=customer_phone,
            name=customer_name,
            last_visit=date_time,
        )

        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to create appointment: %s", exc, exc_info=True)
        return False


def save_call_log(
    db: Client,
    client_id: str,
    caller_phone: str,
    transcript: str,
    summary: str,
    extracted_customer_name: str | None = None,
) -> bool:
    """
    Persist a call log document and optionally upsert the customer.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        caller_phone: Phone number of the caller.
        transcript: Full call transcript.
        summary: Short human-readable summary.
        extracted_customer_name: Customer name extracted during the call (optional).

    Returns:
        True on success, False on failure.
    """
    try:
        now = _utcnow_iso()
        log_id = str(uuid.uuid4())

        log_doc = {
            "id": log_id,
            "client_id": client_id,
            "caller_phone": caller_phone,
            "transcript": transcript,
            "summary": summary,
            "created_at": now,
        }

        db.collection("call_logs").document(log_id).set(log_doc)
        logger.info("Call log %s saved for client %s", log_id, client_id)

        # If a customer name was extracted, update / create the customer record
        if extracted_customer_name:
            upsert_customer(
                db=db,
                client_id=client_id,
                phone=caller_phone,
                name=extracted_customer_name,
            )

        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save call log: %s", exc, exc_info=True)
        return False
