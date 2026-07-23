"""Invite token + code generation and hashing.

Mirrors the frontend's opaque single-use invite concept (``frontend/src/lib/
tokens.js``): the token/code are unguessable random handles that carry no data;
the ``invitations`` table is the source of truth for what they map to and
whether they are still valid.

Two artifacts are minted per invite:

* **token** — high-entropy (``secrets.token_urlsafe``), embedded in the magic
  link ``/join/<token>``.
* **code** — a short, human-typable string for manual entry when the resident
  can't use the link.

Only SHA-256 **hashes** are stored. Because both values are server-generated and
random (not user-chosen secrets), a fast hash is appropriate; single-use,
expiry, and phone matching provide the additional guardrails around the shorter
code.
"""

from __future__ import annotations

import hashlib
import secrets

# Characters for the typable code: no 0/O/1/I/L ambiguity.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8


def generate_token() -> str:
    """Return a URL-safe, high-entropy invite token for the magic link."""
    return secrets.token_urlsafe(32)


def generate_code() -> str:
    """Return a short, human-typable invite code (e.g. 'K7M2QPR9')."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def hash_secret(value: str) -> str:
    """Return the hex SHA-256 hash of ``value`` for at-rest storage."""
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def normalize_code(value: str) -> str:
    """Normalize a user-entered code for comparison (upper, no spaces)."""
    return value.strip().replace(" ", "").upper()
