"""Create confirmed QA sign-in accounts directly through the Supabase Admin API.

    python scripts/seed_test_accounts.py --email qa@test.local --password 'QaSeed!2026'
    python scripts/seed_test_accounts.py --batch 5 --prefix qa
    python scripts/seed_test_accounts.py --batch 5 --prefix qa --dry-run

LOCAL / QA ONLY. NEVER POINT THIS AT PRODUCTION.
================================================

This script authenticates with the **service-role key** read from
``backend/.env`` (``SUPABASE_SERVICE_ROLE_KEY``). That key bypasses row-level
security on every table in the project and can mint confirmed users at will.
Three consequences, all of them the reason this file is a hand-run tool and not
an endpoint:

* Whichever project that ``.env`` points at is the project this writes to. Check
  ``SUPABASE_URL`` before every run. There is no confirmation prompt, because a
  prompt is not a safety mechanism -- reading the URL is.
* The accounts it creates are real, confirmed, sign-in-capable users. They are
  litter in any database that is not a throwaway one.
* Never commit real credentials -- not into this file, not into a shell history
  you paste anywhere, not into an issue. The default password below is a public
  string precisely so that nobody is tempted to put a real one here.

WHY THIS EXISTS (issue #53)
---------------------------
Signing QA testers up through the product's own flow goes through GoTrue's
signup path, which rate-limits by IP and by email domain and then leaves each
account waiting on a confirmation mail nobody receives at ``@test.local``.
``auth.admin.create_user`` with ``email_confirm=True`` sidesteps both problems:
it is the admin path, so no signup rate limit applies, and the account is born
confirmed and can sign in immediately.

WHAT IT DOES NOT DO
-------------------
It creates **auth users only**. It does not create a profile, a community, a
membership or a residency -- those are the product's own onboarding, and a QA
run that skipped them would be testing a shape the app never produces. Seed the
account here, then join or create a community through the UI as the tester.

IDEMPOTENCE
-----------
An email that already exists is reported and skipped, not treated as a failure:
re-running the same command after adding one more tester is the normal way to
use this. Only a genuine error (a bad key, an unreachable project, a rejected
password) makes the run exit non-zero.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

#: The domain batch accounts are minted under. `.local` is reserved by RFC 6762
#: and resolves nowhere, so no mail these addresses would receive can leave the
#: machine -- which is safe here only because `email_confirm=True` means none is
#: ever sent.
DEFAULT_DOMAIN = "test.local"

#: A deliberately public password. It is written down in this file, in the
#: repository, on purpose: a QA account is a throwaway, and a *secret* default
#: would invite somebody to reuse this script somewhere it matters.
DEFAULT_PASSWORD = "QaSeed!2026"

#: What GoTrue says when the address is taken. Matched case-insensitively
#: against both the error's message and its `code`/`error_code`, because the
#: SDK has moved that detail between fields across versions.
_ALREADY_REGISTERED = (
    "already been registered",
    "already registered",
    "already exists",
    "email_exists",
    "user_already_exists",
)

CREATED = "created"
EXISTS = "exists"


def build_parser() -> argparse.ArgumentParser:
    """The CLI. One account or a batch, never both and never neither."""
    parser = argparse.ArgumentParser(
        prog="seed_test_accounts.py",
        description=(
            "Create confirmed QA sign-in accounts through the Supabase Admin "
            "API. LOCAL/QA ONLY -- this uses the service-role key."
        ),
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--email", help="create exactly this one account")
    target.add_argument(
        "--batch",
        type=int,
        metavar="N",
        help=f"create N accounts named <prefix>1@{DEFAULT_DOMAIN} .. <prefix>N@...",
    )
    parser.add_argument(
        "--prefix", default="qa", help="batch name prefix (default: qa)"
    )
    parser.add_argument(
        "--domain",
        default=DEFAULT_DOMAIN,
        help=f"batch email domain (default: {DEFAULT_DOMAIN})",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"password for every account created (default: {DEFAULT_PASSWORD})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the accounts that would be created and call nothing",
    )
    return parser


def plan_accounts(args: argparse.Namespace) -> list[tuple[str, str]]:
    """The (email, password) pairs one invocation would create.

    Built and printed before anything is called, so ``--dry-run`` shows the
    exact set and a real run cannot surprise anybody with a name it derived
    differently.
    """
    if args.email:
        return [(args.email.strip().lower(), args.password)]

    if args.batch < 1:
        raise SystemExit("--batch must be at least 1")

    return [
        (f"{args.prefix}{index}@{args.domain}".lower(), args.password)
        for index in range(1, args.batch + 1)
    ]


def _is_already_registered(error: Exception) -> bool:
    """Whether ``error`` is GoTrue saying the address is taken.

    Matched on text rather than on an exception class: the SDK raises
    ``AuthApiError`` for a bad key and for a duplicate email alike, so the class
    does not distinguish them, and importing it here would tie this script to
    one SDK version for no benefit.
    """
    haystack = " ".join(
        str(getattr(error, attribute, "") or "")
        for attribute in ("message", "code", "error_code")
    )
    haystack = f"{haystack} {error}".lower()
    return any(phrase in haystack for phrase in _ALREADY_REGISTERED)


def seed_account(client: object, email: str, password: str) -> str:
    """Create one confirmed account. Returns ``"created"`` or ``"exists"``.

    ``email_confirm=True`` is the whole point of using the admin path: the user
    is born confirmed, so it can sign in at once and no mail is sent to an
    address that does not resolve.
    """
    try:
        client.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
    except Exception as error:  # noqa: BLE001 - the message is the report
        if _is_already_registered(error):
            return EXISTS
        raise
    return CREATED


def _service_client():
    """The repository's service-role client.

    Imported here rather than at module scope so that ``--help`` and
    ``--dry-run`` work without a configured ``.env``, and so the unit tests can
    exercise every path without a Supabase project.
    """
    from app.core.supabase_client import get_service_client

    return get_service_client()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    accounts = plan_accounts(args)

    if args.dry_run:
        print(f"dry run -- {len(accounts)} account(s) would be created:")
        for email, _ in accounts:
            print(f"  would create  {email}")
        return 0

    client = _service_client()

    created = existing = failed = 0
    for email, password in accounts:
        try:
            outcome = seed_account(client, email, password)
        except Exception as error:  # noqa: BLE001 - one bad row must not stop the run
            failed += 1
            print(f"  FAILED        {email}: {error}", file=sys.stderr)
            continue
        if outcome == CREATED:
            created += 1
            print(f"  created       {email}")
        else:
            existing += 1
            print(f"  already there {email}")

    print(f"{created} created, {existing} already existed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
