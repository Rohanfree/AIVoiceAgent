"""
calendar_service.py — Handles interactions with Google Calendar API.
"""

import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleAuthRequest
from app.config import settings
from app.services.token_crypto import (
    TokenEncryptionError,
    decrypt_token_data,
    firestore_token_write,
    is_legacy_plaintext,
)

logger = logging.getLogger(__name__)

def get_calendar_service(token_data: dict):
    """
    Build a Google Calendar service object from stored token data.
    Refreshes the token if expired.
    """
    try:
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing Google OAuth token...")
            creds.refresh(GoogleAuthRequest())
            # Caller handles saving new tokens back to Firestore if needed
        
        service = build("calendar", "v3", credentials=creds)
        return service, creds
    except Exception as e:
        logger.error("Failed to build Google Calendar service: %s", e)
        return None, None

async def create_calendar_event(db, client_id: str, appointment_data: dict) -> bool:
    """
    Create a Google Calendar event for a confirmed appointment.
    """
    try:
        # 1. Get tokens from Firestore
        client_doc = db.collection("clients").document(client_id).get()
        if not client_doc.exists:
            return False
        
        client_data = client_doc.to_dict()
        if not client_data.get("google_calendar_linked"):
            logger.info("Google Calendar not linked for client %s, skipping sync.", client_id)
            return False
        
        stored_tokens = client_data.get("google_calendar_tokens")
        if not stored_tokens:
            return False

        try:
            token_data = decrypt_token_data(stored_tokens, client_id)
            if is_legacy_plaintext(stored_tokens):
                # Migrate legacy plaintext to the encrypted envelope on first read.
                write = firestore_token_write(token_data, client_id)
                db.collection("clients").document(client_id).set(write["data"], merge=write["merge"])
                logger.info("Migrated Google tokens to encrypted storage for client %s", client_id)
        except TokenEncryptionError as e:
            logger.error("Cannot use stored Google tokens for client %s: %s", client_id, e)
            return False

        # 2. Get service
        service, updated_creds = get_calendar_service(token_data)
        if not service:
            return False
        
        # 3. Handle Token Update if refreshed
        if updated_creds and updated_creds.token != token_data.get("token"):
             logger.info("Updating refreshed tokens in Firestore for client %s", client_id)
             token_data["token"] = updated_creds.token
             write = firestore_token_write(token_data, client_id)
             db.collection("clients").document(client_id).set(write["data"], merge=write["merge"])

        # 4. Prepare Event
        start_dt_str = appointment_data.get("date_time")
        duration = appointment_data.get("duration_minutes", 30)

        # Strip any timezone offset so the time is treated as local (not UTC-converted)
        start_dt = datetime.fromisoformat(start_dt_str).replace(tzinfo=None)
        end_dt = start_dt + timedelta(minutes=duration)

        # Use the calendar's own timezone so the time displays without conversion
        calendar_info = service.calendars().get(calendarId='primary').execute()
        calendar_tz = calendar_info.get('timeZone', 'UTC')

        event = {
            'summary': f"Appointment: {appointment_data.get('customer_name')} - {appointment_data.get('service_name')}",
            'description': f"Automated booking for {appointment_data.get('customer_name')}\nPhone: {appointment_data.get('customer_phone')}",
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': calendar_tz,
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': calendar_tz,
            },
            'reminders': {
                'useDefault': True,
            },
        }

        # 5. Insert Event
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        logger.info("Google Calendar event created: %s", created_event.get('htmlLink'))
        
        # Save eventId back to appointment for future edits/cancellations
        appt_id = appointment_data.get("id")
        if appt_id:
             db.collection("appointments").document(appt_id).set({
                 "google_event_id": created_event.get("id"),
                 "google_event_link": created_event.get("htmlLink")
             }, merge=True)

        return True

    except Exception as e:
        logger.error("Error creating Google Calendar event: %s", e)
        return False
