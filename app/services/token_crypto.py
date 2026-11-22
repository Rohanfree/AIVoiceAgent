"""
token_crypto.py - Authenticated encryption for Google OAuth credentials at rest.

Stored shape (Firestore field ``google_calendar_tokens``):

    {"enc_v": 1, "ct": "<urlsafe-b64(nonce || AES-256-GCM ciphertext+tag)>"}

The key is derived from ``settings.secret_key`` with HKDF-SHA256. The client id
is bound as associated data, so a blob copied onto another tenant's document
fails authentication. Plaintext token values are never logged or put into
exception messages.
"""

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

ENVELOPE_VERSION = 1
_NONCE_BYTES = 12
_HKDF_INFO = b"automite-google-tokens-v1"
_AAD_PREFIX = b"google_calendar_tokens:v1:"

# Fields that make up a legacy plaintext record.
_LEGACY_MARKERS = ("token", "refresh_token")


class TokenEncryptionError(Exception):
    """Encryption or decryption failed. Messages never contain secret material."""


def _key() -> bytes:
    secret = (settings.secret_key or "").strip()
    if not secret:
        raise TokenEncryptionError("SECRET_KEY is not configured; cannot protect Google tokens")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        secret.encode()
    )


def _aad(client_id: str) -> bytes:
    return _AAD_PREFIX + client_id.encode()


def is_encrypted(stored: object) -> bool:
    return isinstance(stored, dict) and "enc_v" in stored and "ct" in stored


def is_legacy_plaintext(stored: object) -> bool:
    return (
        isinstance(stored, dict)
        and not is_encrypted(stored)
        and any(k in stored for k in _LEGACY_MARKERS)
    )


def encrypt_token_data(token_data: dict, client_id: str) -> dict:
    """Return the envelope to persist in place of the plaintext token dict."""
    key = _key()
    nonce = os.urandom(_NONCE_BYTES)
    plaintext = json.dumps(token_data, separators=(",", ":")).encode()
    ct = AESGCM(key).encrypt(nonce, plaintext, _aad(client_id))
    return {"enc_v": ENVELOPE_VERSION, "ct": base64.urlsafe_b64encode(nonce + ct).decode()}


def decrypt_token_data(stored: dict, client_id: str) -> dict:
    """Decrypt an envelope; legacy plaintext records are returned as-is (see is_legacy_plaintext)."""
    if is_legacy_plaintext(stored):
        return stored
    if not is_encrypted(stored):
        raise TokenEncryptionError("Unrecognised stored token format")
    if stored.get("enc_v") != ENVELOPE_VERSION:
        raise TokenEncryptionError("Unsupported token envelope version")
    key = _key()
    try:
        raw = base64.urlsafe_b64decode(stored["ct"])
        if len(raw) <= _NONCE_BYTES:
            raise ValueError
        plaintext = AESGCM(key).decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], _aad(client_id))
        data = json.loads(plaintext)
    except (InvalidTag, ValueError, TypeError):
        raise TokenEncryptionError("Stored Google tokens failed authentication") from None
    if not isinstance(data, dict):
        raise TokenEncryptionError("Stored Google tokens failed authentication")
    return data


def firestore_token_write(token_data: dict, client_id: str) -> dict:
    """Fields + merge spec for ``doc.set(...)`` that replace the stored token map wholesale.

    A plain ``merge=True`` would deep-merge into a legacy plaintext map and leave
    its token keys in Firestore; listing the field path replaces the whole value.
    """
    return {
        "data": {
            "google_calendar_linked": True,
            "google_calendar_tokens": encrypt_token_data(token_data, client_id),
        },
        "merge": ["google_calendar_linked", "google_calendar_tokens"],
    }

