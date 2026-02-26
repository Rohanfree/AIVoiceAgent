"""
availability_service.py - Logic for checking appointment slot availability
and computing the next available time window.
"""

import logging
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import Client

logger = logging.getLogger(__name__)


# ─── Helper: overlap check ─────────────────────────────────────────────────

def _slots_overlap(
    existing_start: datetime,
    existing_duration_minutes: int,
    requested_start: datetime,
    requested_duration_minutes: int,
) -> bool:
    """
    Returns True if two time intervals overlap.

    Interval A: [existing_start, existing_start + existing_duration)
    Interval B: [requested_start, requested_start + requested_duration)
    """
    existing_end = existing_start + timedelta(minutes=existing_duration_minutes)
    requested_end = requested_start + timedelta(minutes=requested_duration_minutes)

    return requested_start < existing_end and requested_end > existing_start


# ─── Fetch service duration ────────────────────────────────────────────────

def get_service_duration(
    db: Client, client_id: str, service_name: str
) -> int | None:
    """
    Look up the duration (in minutes) of a named service for a given client.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        service_name: Exact name of the service.

    Returns:
        Duration in minutes, or None if client/service not found.
    """
    client_doc = db.collection("clients").document(client_id).get()
    if not client_doc.exists:
        logger.warning("Client not found: %s", client_id)
        return None

    services: list[dict] = client_doc.to_dict().get("services", [])
    for svc in services:
        if svc.get("name", "").lower() == service_name.lower():
            logger.debug(
                "Service '%s' found with duration %s min", service_name, svc["duration"]
            )
            return int(svc["duration"])

    logger.warning("Service '%s' not found for client %s", service_name, client_id)
    return None


# ─── Pull conflicting appointments ────────────────────────────────────────

def _get_appointments_on_date(
    db: Client, client_id: str, date: datetime
) -> list[dict]:
    """
    Fetch all active (confirmed/pending) appointments for a client on the given date.

    Firestore requires a composite index for range queries on multiple fields.
    To avoid that, we query ONLY by client_id (single equality filter), then
    filter by date range and status entirely in Python.
    """
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    day_start_iso = day_start.isoformat()
    day_end_iso = day_end.isoformat()

    # Single-field query — no composite index needed
    docs = (
        db.collection("appointments")
        .where("client_id", "==", client_id)
        .stream()
    )

    active_statuses = {"confirmed", "pending"}
    results = []
    for doc in docs:
        data = doc.to_dict()
        appt_time = data.get("date_time", "")
        status = data.get("status", "")
        # Filter by date window and active status in Python
        if status in active_statuses and day_start_iso <= appt_time < day_end_iso:
            results.append(data)

    logger.debug(
        "Found %d active appointments for client %s on %s",
        len(results),
        client_id,
        day_start_iso,
    )
    return results


# ─── Main availability check ───────────────────────────────────────────────

def check_slot_availability(
    db: Client,
    client_id: str,
    service_name: str,
    requested_dt: datetime,
    duration_minutes: int,
) -> tuple[bool, str | None]:
    """
    Determine whether the requested slot is free.

    Args:
        db: Firestore client.
        client_id: Business client identifier.
        service_name: Name of the service (used for logging).
        requested_dt: timezone-aware datetime of the desired slot start.
        duration_minutes: Duration of the requested service.

    Returns:
        (is_available, next_available_iso)
        - If available: (True, None)
        - If not:       (False, ISO string of next suggested time)
    """
    appointments = _get_appointments_on_date(db, client_id, requested_dt)

    busy_intervals: list[tuple[datetime, int]] = []

    for appt in appointments:
        try:
            appt_start = datetime.fromisoformat(appt["date_time"])
            # Ensure timezone awareness
            if appt_start.tzinfo is None:
                appt_start = appt_start.replace(tzinfo=timezone.utc)
            # We don't store per-appointment duration; use the service duration
            # stored inside the appointment for overlap checking if available,
            # otherwise fall back to the requested service duration as a safe estimate.
            appt_duration = int(appt.get("duration_minutes", duration_minutes))
            busy_intervals.append((appt_start, appt_duration))
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed appointment: %s (%s)", appt, exc)

    # Check if requested slot is free
    req_start = requested_dt
    if req_start.tzinfo is None:
        req_start = req_start.replace(tzinfo=timezone.utc)

    for busy_start, busy_duration in busy_intervals:
        if _slots_overlap(busy_start, busy_duration, req_start, duration_minutes):
            # Not available — compute next free slot
            next_slot = _find_next_available(
                busy_intervals, req_start, duration_minutes
            )
            logger.info(
                "Slot at %s not available. Next: %s", req_start.isoformat(), next_slot
            )
            return False, next_slot

    logger.info("Slot at %s is available.", req_start.isoformat())
    return True, None


# ─── Next available time finder ────────────────────────────────────────────

def _find_next_available(
    busy_intervals: list[tuple[datetime, int]],
    from_dt: datetime,
    duration_minutes: int,
    increment_minutes: int = 15,
    max_search_hours: int = 24,
) -> str:
    """
    Starting from `from_dt`, scan forward in `increment_minutes` steps until
    we find a gap that fits `duration_minutes`.

    Args:
        busy_intervals: List of (start_datetime, duration_minutes) tuples.
        from_dt: Earliest point to start looking.
        duration_minutes: Duration the free slot must accommodate.
        increment_minutes: Step size when scanning forward (default 15 min).
        max_search_hours: Give up after this many hours (avoid infinite loop).

    Returns:
        ISO 8601 string of the next available slot start.
    """
    candidate = from_dt + timedelta(minutes=increment_minutes)
    deadline = from_dt + timedelta(hours=max_search_hours)

    while candidate < deadline:
        conflict = any(
            _slots_overlap(bs, bd, candidate, duration_minutes)
            for bs, bd in busy_intervals
        )
        if not conflict:
            return candidate.isoformat()
        candidate += timedelta(minutes=increment_minutes)

    # Fallback: return first slot after all busy periods the next day
    return (from_dt + timedelta(hours=max_search_hours)).isoformat()
