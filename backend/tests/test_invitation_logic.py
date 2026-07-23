"""Unit tests for the pure invite-redemption decision and token hashing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core import tokens
from app.services.invitation_service import evaluate_invitation

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _invite(**overrides: object) -> dict:
    base = {
        "id": "inv-1",
        "redeemed_at": None,
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "role": "RESIDENT",
        "apartment_id": "B-1204",
    }
    base.update(overrides)
    return base


def test_valid_invite_returns_none() -> None:
    assert evaluate_invitation(_invite(), now=NOW) is None


def test_missing_invite_is_invalid() -> None:
    assert evaluate_invitation(None, now=NOW) == "invalid"


def test_redeemed_invite_is_used() -> None:
    invite = _invite(redeemed_at=NOW.isoformat())
    assert evaluate_invitation(invite, now=NOW) == "used"


def test_expired_invite_is_expired() -> None:
    invite = _invite(expires_at=(NOW - timedelta(hours=1)).isoformat())
    assert evaluate_invitation(invite, now=NOW) == "expired"


def test_naive_expiry_is_treated_as_utc() -> None:
    invite = _invite(expires_at="2026-07-22T11:00:00")  # 1h before NOW, no tz
    assert evaluate_invitation(invite, now=NOW) == "expired"


def test_hash_is_stable_and_matches() -> None:
    token = tokens.generate_token()
    assert tokens.hash_secret(token) == tokens.hash_secret(token)


def test_code_normalization_round_trip() -> None:
    code = tokens.generate_code()
    typed = f"  {code.lower()} "
    assert tokens.hash_secret(tokens.normalize_code(typed)) == tokens.hash_secret(code)


def test_generated_code_uses_unambiguous_alphabet() -> None:
    code = tokens.generate_code()
    assert len(code) == 8
    assert not (set(code) & set("O0I1L"))
