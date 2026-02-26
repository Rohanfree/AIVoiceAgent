"""
db.py - Firebase Admin SDK initialization and Firestore dependency injection.
"""

import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client

from app.config import settings

logger = logging.getLogger(__name__)


def _initialize_firebase() -> None:
    """Initialize Firebase app once. Safe to call multiple times."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.firebase_credential_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized from: %s", settings.firebase_credential_path)


@lru_cache(maxsize=1)
def get_firestore_client() -> Client:
    """
    Returns a cached Firestore client.
    The lru_cache ensures we reuse the same client instance across requests.
    """
    _initialize_firebase()
    return firestore.client()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Client:
    """
    FastAPI dependency that yields a Firestore client.
    Use this with Depends(get_db) in your route handlers.
    """
    return get_firestore_client()
