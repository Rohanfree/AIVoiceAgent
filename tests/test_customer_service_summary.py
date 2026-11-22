"""
Minimal test for get_last_call_summary — verifies it returns the most recent
summary without relying on a Firestore composite index (no order_by in query).
"""
import unittest
from unittest.mock import MagicMock


def _make_doc(client_id, phone, created_at, summary):
    doc = MagicMock()
    doc.to_dict.return_value = {
        "client_id": client_id,
        "true_caller_phone": phone,
        "created_at": created_at,
        "summary": summary,
    }
    return doc


class TestGetLastCallSummary(unittest.TestCase):

    def _make_db(self, docs):
        db = MagicMock()
        (
            db.collection.return_value
            .where.return_value
            .where.return_value
            .stream.return_value
        ) = iter(docs)
        return db

    def test_returns_most_recent_summary(self):
        from app.services.customer_service import get_last_call_summary

        docs = [
            _make_doc("c1", "111", "2026-04-14T10:00:00+00:00", "older summary"),
            _make_doc("c1", "111", "2026-04-15T10:00:00+00:00", "newer summary"),
        ]
        db = self._make_db(docs)
        result = get_last_call_summary(db, "c1", "111")
        self.assertEqual(result, "newer summary")

    def test_returns_none_when_no_logs(self):
        from app.services.customer_service import get_last_call_summary

        db = self._make_db([])
        result = get_last_call_summary(db, "c1", "111")
        self.assertIsNone(result)

    def test_returns_none_on_firestore_error(self):
        from app.services.customer_service import get_last_call_summary

        db = MagicMock()
        db.collection.side_effect = Exception("Firestore unavailable")
        result = get_last_call_summary(db, "c1", "111")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
