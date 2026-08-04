"""Print a fresh VAPID keypair for one environment.

    python scripts/generate_vapid_keys.py

Writes three lines to stdout and **no file**. Copy them into that environment's
``.env`` (or its secret store) yourself.

WHO RUNS THIS

The person who already holds that environment's ``SUPABASE_SERVICE_ROLE_KEY``.
The keypair is an ops artifact, not a build artifact, and the two secrets belong
to the same custodian for the reason in ``RESIDENT_BACKEND_DESIGN.md`` §10.5:
the service-role key bypasses row-level security on every table in the project
and is strictly the more valuable of the two. Splitting them across two people
protects neither.

**One pair per environment, never shared.** A subscription is bound to the key
that created it, so a development key used in production means a laptop can push
to real residents' phones.

WHY THIS IS NOT DONE AT BOOT

``applicationServerKey`` is baked into every browser subscription at
``PushManager.subscribe`` time. A key generated at startup would silently
invalidate every stored subscription on each restart, and with several uvicorn
workers each would generate a different one, so pushes would fail at random
rather than fail visibly.

ROTATION IS AN INCIDENT RESPONSE, NOT HYGIENE

Replacing these values unsubscribes every browser *silently* -- no error, pushes
simply stop arriving, because the protocol has no dual-key period. The only
mitigation is on the client: compare ``GET /push/vapid-key`` against the stored
``applicationServerKey`` on load and re-subscribe when they differ (§10.6).
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from py_vapid import Vapid01, b64urlencode
    except ImportError:
        print(
            "py-vapid is not installed. It ships with pywebpush:\n"
            "    pip install -e .[dev]",
            file=sys.stderr,
        )
        return 1

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    vapid = Vapid01()
    vapid.generate_keys()

    # base64url, unpadded, single line -- the raw P-256 private scalar and the
    # uncompressed public point. That is exactly what py-vapid, pywebpush and
    # the browser's `applicationServerKey` all want, and it is why these are not
    # PEMs: a PEM in an environment variable needs newline escaping, and escaped
    # newlines are how a key gets corrupted in a CI secret store at 2am.
    private_key = vapid.private_key
    assert private_key is not None  # generate_keys() just set it
    raw_private = private_key.private_numbers().private_value.to_bytes(32, "big")
    raw_public = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    assert isinstance(private_key.curve, ec.SECP256R1)  # Web Push is P-256 only

    print(f"VAPID_PUBLIC_KEY={b64urlencode(raw_public)}")
    print(f"VAPID_PRIVATE_KEY={b64urlencode(raw_private)}")
    print("VAPID_SUBJECT=mailto:admin@example.com  # replace with a real contact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
