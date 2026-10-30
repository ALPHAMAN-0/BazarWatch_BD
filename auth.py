"""Password hashing for BazarWatch BD.

Uses only the standard library: a random salt, PBKDF2-HMAC-SHA256 for the
hash, and ``hmac.compare_digest`` for a timing-safe comparison.

No password is ever stored or logged in plain text.
"""

from __future__ import annotations

import hashlib
import hmac
import os

# Number of PBKDF2 rounds. High enough to be slow to brute-force, low enough
# that a classroom demo stays responsive.
ITERATIONS = 200_000
SALT_BYTES = 16
KEY_LENGTH = 32
DIGEST = "sha256"


def hash_password(password: str) -> tuple[str, str]:
    """Hash ``password`` with a fresh random salt.

    Returns ``(salt_hex, hash_hex)``.  Both are hex strings so they can be
    stored safely in JSON.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        DIGEST, password.encode("utf-8"), salt, ITERATIONS, dklen=KEY_LENGTH
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """Check ``password`` against a stored salt and hash.

    Returns False for any malformed input instead of raising, so a corrupt
    user file can never crash the login screen.
    """
    if not isinstance(password, str) or not password:
        return False
    if not isinstance(salt, str) or not isinstance(password_hash, str):
        return False
    try:
        salt_bytes = bytes.fromhex(salt)
        expected = bytes.fromhex(password_hash)
    except ValueError:
        return False
    if not salt_bytes or not expected:
        return False
    digest = hashlib.pbkdf2_hmac(
        DIGEST, password.encode("utf-8"), salt_bytes, ITERATIONS, dklen=len(expected)
    )
    return hmac.compare_digest(digest, expected)
