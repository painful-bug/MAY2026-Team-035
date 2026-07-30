"""Test-wide setup.

Its only job is to make ``app.main`` importable. ``Settings`` requires four
Supabase values and is constructed at import time, so without these the whole
app module raises before a single test runs.

The values are placeholders and nothing here opens a connection: the tests that
import the app inspect its *shape* -- which routes exist, what the generated
OpenAPI document says -- and never make a request to Supabase.
"""

from __future__ import annotations

import os

# `setdefault`, not assignment: a developer with a real .env in their environment
# keeps it, and these only fill the gaps.
for _key, _value in {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "placeholder-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "placeholder-service-role-key",
    "SUPABASE_JWT_SECRET": "placeholder-jwt-secret",
}.items():
    os.environ.setdefault(_key, _value)
