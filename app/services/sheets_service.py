"""
sheets_service.py - Append Vapi call details to a Google Sheet.

Public API
----------
    append_call_to_sheet(call_id, phone, email, duration_seconds, summary)

Authentication
--------------
Uses the same Firebase Service Account JSON that already authenticates
Firestore (FIREBASE_CREDENTIAL_PATH).  The service account must be granted
Editor access to the target spreadsheet and the Google Sheets API must be
enabled on the GCP project.

Sheet format (columns A-F)
--------------------------
    Timestamp (UTC) | Call ID | Phone | Email | Duration (s) | Summary
"""

import logging
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# The only OAuth scope needed for appending rows
_SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_sheets_client():
    """
    Build and return an authenticated Google Sheets API client.

    Re-uses the service-account JSON already on disk for Firestore so no
    additional credentials are required.
    """
    creds = service_account.Credentials.from_service_account_file(
        settings.firebase_credential_path,
        scopes=_SHEETS_SCOPE,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def append_call_to_sheet(
    call_id: str,
    phone: str,
    email: str | None,
    duration_seconds: float | None,
    summary: str | None,
) -> bool:
    """
    Append a single call-log row to the configured Google Sheet.

    Each call is written as one row with the following columns:
        A: Timestamp (UTC ISO 8601)
        B: Call ID
        C: Phone number
        D: Email / Gmail (may be empty)
        E: Duration in seconds (may be empty)
        F: Call summary (may be empty)

    Args:
        call_id:          Unique identifier for the call (e.g. Vapi call ID or
                          the Firestore document ID).
        phone:            Caller's phone number.
        email:            Caller's email / Gmail address.  Pass None if unknown.
        duration_seconds: Total call length in seconds.  Pass None if unknown.
        summary:          Auto-generated or human-written call summary.
                          Pass None if unavailable.

    Returns:
        True  — row appended successfully.
        False — an error occurred (details logged; exception is NOT re-raised so
                the caller's main flow is not interrupted).

    Environment variables required:
        FIREBASE_CREDENTIAL_PATH — path to the service-account JSON file.
        GOOGLE_SHEET_ID          — the Spreadsheet ID from the sheet URL.
        GOOGLE_SHEET_TAB         — worksheet/tab name (default: "Call Logs").

    Example:
        >>> append_call_to_sheet(
        ...     call_id="abc123",
        ...     phone="+1-555-555-1234",
        ...     email="caller@gmail.com",
        ...     duration_seconds=142.5,
        ...     summary="Customer asked about pricing.",
        ... )
        True
    """
    sheet_id = settings.google_sheet_id
    sheet_tab = settings.google_sheet_tab

    if not sheet_id:
        logger.warning(
            "GOOGLE_SHEET_ID is not configured — skipping Sheets append for call %s",
            call_id,
        )
        return False

    timestamp = datetime.now(tz=timezone.utc).isoformat()

    row = [
        timestamp,
        call_id,
        phone or "",
        email or "",
        duration_seconds if duration_seconds is not None else "",
        summary or "",
    ]

    range_notation = f"{sheet_tab}!A:F"

    try:
        client = _get_sheets_client()
        response = (
            client.spreadsheets()
            .values()
            .append(
                spreadsheetId=sheet_id,
                range=range_notation,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )

        updates = response.get("updates", {})
        logger.info(
            "Sheets row appended | call_id=%s | sheet=%s | tab=%s | updatedRange=%s",
            call_id,
            sheet_id,
            sheet_tab,
            updates.get("updatedRange", "unknown"),
        )
        return True

    except HttpError as exc:
        logger.error(
            "Google Sheets API error while appending call %s: %s",
            call_id,
            exc,
            exc_info=True,
        )
        return False

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Unexpected error appending call %s to Sheets: %s",
            call_id,
            exc,
            exc_info=True,
        )
        return False
