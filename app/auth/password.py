"""
password.py — Argon2-based password hashing and verification.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against an Argon2 hash.
    Returns True if the password matches, False otherwise.
    """
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
