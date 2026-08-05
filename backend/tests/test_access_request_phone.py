from pathlib import Path

import pytest

from app.core.exceptions import ValidationError
from app.services.access_request_service import _normal_phone


def test_optional_access_request_phone_is_nullable_and_validated() -> None:
    assert _normal_phone(None) is None
    assert _normal_phone("  ") is None
    assert _normal_phone(" +91 98765-43210 ") == "+919876543210"
    with pytest.raises(ValidationError):
        _normal_phone("9876543210")


def test_legacy_access_request_phone_constraint_is_removed() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "migrations"
        / "20260805154046_make_access_request_phone_optional.sql"
    ).read_text()
    assert "alter column applicant_phone_e164 drop not null" in migration
