"""
sheets_service.py - Google Sheets utilities for the voice-agent platform.

Public API
----------
    create_client_sheet(client_id, business_name, token_data) -> str | None
    append_call_to_sheet(call_id, phone, email, duration_seconds, summary)

Authentication
--------------
create_client_sheet uses per-client OAuth2 credentials supplied as a dict.
append_call_to_sheet uses the Firebase Service Account JSON (FIREBASE_CREDENTIAL_PATH).

Sheet format (columns A-H) created by create_client_sheet
----------------------------------------------------------
    Timestamp (UTC) | Call ID | True Caller Phone | Direct Caller Phone |
    Forwarded From | Duration (s) | Summary | Transcript
"""

import logging
from datetime import datetime, timezone

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# The only OAuth scope needed for appending rows
_SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]

_HEADER_ROW = [
    "Timestamp (UTC)",
    "Call ID",
    "True Caller Phone",
    "Direct Caller Phone",
    "Forwarded From",
    "Duration (s)",
    "Summary",
    "Transcript",
]


def create_client_sheet(
    client_id: str,
    business_name: str,
    token_data: dict,
) -> str | None:
    """
    Create a new Google Sheet in the client's own Google Drive and write a
    bold header row with all call-log columns.

    Args:
        client_id:     Client identifier (used only for logging).
        business_name: Used as part of the spreadsheet title.
        token_data:    Dict with keys: token, refresh_token, token_uri,
                       client_id, client_secret, scopes.

    Returns:
        The new spreadsheetId on success, None on any error.
    """
    try:
        creds = Credentials(
            token=token_data["token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data["token_uri"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            scopes=list(token_data.get("scopes") or _SHEETS_SCOPE),
        )

        if not creds.valid:
            creds.refresh(GoogleAuthRequest())

        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        spreadsheets = service.spreadsheets()

        title = f"{business_name} - Call Logs"
        create_resp = spreadsheets.create(
            body={"properties": {"title": title}},
            fields="spreadsheetId",
        ).execute()
        sheet_id = create_resp["spreadsheetId"]

        # Write header row
        spreadsheets.values().update(
            spreadsheetId=sheet_id,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [_HEADER_ROW]},
        ).execute()

        # Bold the header row
        num_cols = len(_HEADER_ROW)
        spreadsheets.batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": 0,
                                "startRowIndex": 0,
                                "endRowIndex": 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": num_cols,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True}
                                }
                            },
                            "fields": "userEnteredFormat.textFormat.bold",
                        }
                    }
                ]
            },
        ).execute()

        logger.info(
            "Google Sheet created | client=%s | sheet_id=%s | title=%s",
            client_id,
            sheet_id,
            title,
        )
        return sheet_id

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to create Google Sheet for client %s: %s",
            client_id,
            exc,
            exc_info=True,
        )
        return None


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
