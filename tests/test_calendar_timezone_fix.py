"""Test that calendar events are created without timezone conversion."""
import unittest
from unittest.mock import MagicMock, patch
import asyncio
from app.services.calendar_service import create_calendar_event


class TestCalendarTimezone(unittest.TestCase):
    def test_event_has_no_timezone_field(self):
        db = MagicMock()
        client_doc = MagicMock()
        client_doc.exists = True
        client_doc.to_dict.return_value = {
            "google_calendar_linked": True,
            "google_calendar_tokens": {
                "token": "tok",
                "refresh_token": "ref",
                "token_uri": "uri",
                "client_id": "cid",
                "client_secret": "sec",
                "scopes": [],
            },
        }
        db.collection.return_value.document.return_value.get.return_value = client_doc

        captured_event = {}

        def fake_insert(calendarId, body):
            captured_event.update(body)
            mock_exec = MagicMock()
            mock_exec.execute.return_value = {"id": "evt1", "htmlLink": "http://example.com"}
            return mock_exec

        mock_service = MagicMock()
        mock_service.events.return_value.insert.side_effect = fake_insert
        mock_service.calendars.return_value.get.return_value.execute.return_value = {"timeZone": "Asia/Kolkata"}

        with patch("app.services.calendar_service.get_calendar_service", return_value=(mock_service, None)):
            appointment_data = {
                "date_time": "2026-04-20T14:00:00",
                "duration_minutes": 30,
                "customer_name": "Alice",
                "customer_phone": "+1234567890",
                "service_name": "Haircut",
                "id": "appt_1",
            }
            asyncio.run(create_calendar_event(db, "client_1", appointment_data))

        self.assertEqual(captured_event["start"]["timeZone"], "Asia/Kolkata", "timeZone must come from calendar, not be hardcoded UTC")
        self.assertEqual(captured_event["end"]["timeZone"], "Asia/Kolkata")
        self.assertEqual(captured_event["start"]["dateTime"], "2026-04-20T14:00:00")


if __name__ == "__main__":
    unittest.main()
