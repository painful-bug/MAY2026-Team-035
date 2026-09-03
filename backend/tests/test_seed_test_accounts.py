"""`scripts/seed_test_accounts.py` -- the QA account seeder, with the Supabase
client entirely faked out.

**Nothing here touches a network.** The subject is the script's decisions -- what
it plans to create, what it sends, and what it does when the address is already
taken -- and every one of them is observable from a stand-in client that records
its calls. The script's one real dependency, `get_service_client()`, is reached
only through `_service_client()`, which these tests replace; a test that
accidentally built a real client would try to authenticate with whatever
`.env` the machine happens to have, which is exactly the accident the script's
header warns about.

The half that cannot be tested here is the half that needs a Supabase project:
that `email_confirm=True` really does bypass the signup rate limit, and that the
resulting user can sign in. The owner runs the script to find that out; issue
#53.
"""

from __future__ import annotations

import pytest

from scripts import seed_test_accounts as seed


class _Admin:
    """Records every `create_user` payload, and raises what it is told to."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def create_user(self, attributes: dict) -> object:
        self.calls.append(attributes)
        if self.error is not None:
            raise self.error
        return object()


class _Client:
    def __init__(self, error: Exception | None = None) -> None:
        self.auth = type("_Auth", (), {"admin": _Admin(error)})()


class _Exploding:
    """A client that fails the moment anything is read off it.

    `--dry-run` must not merely avoid *calling* Supabase; it must avoid
    *reaching* for it, because building the client is itself the step that reads
    the service-role key.
    """

    def __getattr__(self, name: str) -> object:  # pragma: no cover - the point
        raise AssertionError(f"the client was touched: .{name}")


class _AuthApiError(Exception):
    """Shaped like the SDK's error: a `message` and a `code` beside the text."""

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _args(argv: list[str]):
    return seed.build_parser().parse_args(argv)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def test_one_email_plans_exactly_that_account() -> None:
    plan = seed.plan_accounts(
        _args(["--email", "QA@Test.Local", "--password", "s3cret"])
    )
    assert plan == [("qa@test.local", "s3cret")]


def test_a_batch_is_numbered_from_one_under_the_prefix() -> None:
    """`qa1@test.local` .. `qaN@test.local` -- the naming the QA notes assume,
    one-based because there is no `qa0` tester."""
    plan = seed.plan_accounts(_args(["--batch", "3", "--prefix", "qa"]))

    assert [email for email, _ in plan] == [
        "qa1@test.local",
        "qa2@test.local",
        "qa3@test.local",
    ]
    assert {password for _, password in plan} == {seed.DEFAULT_PASSWORD}


def test_the_batch_domain_and_prefix_are_overridable() -> None:
    plan = seed.plan_accounts(
        _args(["--batch", "2", "--prefix", "tester", "--domain", "example.invalid"])
    )
    assert [email for email, _ in plan] == [
        "tester1@example.invalid",
        "tester2@example.invalid",
    ]


def test_email_and_batch_are_mutually_exclusive_and_one_is_required() -> None:
    """Both would be ambiguous; neither would be a no-op that looks like a
    success. argparse refuses each with exit code 2."""
    with pytest.raises(SystemExit):
        _args(["--email", "a@test.local", "--batch", "2"])
    with pytest.raises(SystemExit):
        _args([])


def test_an_empty_batch_is_refused() -> None:
    with pytest.raises(SystemExit):
        seed.plan_accounts(_args(["--batch", "0"]))


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_dry_run_never_builds_a_client(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """It prints the plan and returns 0 without reaching for the service-role
    key at all."""
    monkeypatch.setattr(seed, "_service_client", lambda: _Exploding())

    assert seed.main(["--batch", "2", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "dry run" in out
    assert "qa1@test.local" in out
    assert "qa2@test.local" in out


# ---------------------------------------------------------------------------
# What is actually sent
# ---------------------------------------------------------------------------


def test_the_account_is_created_confirmed() -> None:
    """`email_confirm=True` is the reason this script exists: it is what makes
    the admin path skip the signup rate limit and the confirmation mail that
    would never arrive at `@test.local`."""
    client = _Client()

    assert seed.seed_account(client, "qa1@test.local", "pw") == seed.CREATED
    assert client.auth.admin.calls == [
        {"email": "qa1@test.local", "password": "pw", "email_confirm": True}
    ]


def test_main_creates_every_planned_account(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    client = _Client()
    monkeypatch.setattr(seed, "_service_client", lambda: client)

    assert seed.main(["--batch", "3"]) == 0

    assert [call["email"] for call in client.auth.admin.calls] == [
        "qa1@test.local",
        "qa2@test.local",
        "qa3@test.local",
    ]
    assert all(call["email_confirm"] is True for call in client.auth.admin.calls)
    assert "3 created, 0 already existed, 0 failed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        _AuthApiError("A user with this email address has already been registered"),
        _AuthApiError("Database error", code="email_exists"),
        ValueError("user_already_exists"),
    ],
)
def test_an_existing_email_is_reported_not_fatal(error: Exception) -> None:
    """Re-running the command after adding one more tester is the normal way to
    use this script, so the addresses that are already there must not stop it."""
    client = _Client(error)

    assert seed.seed_account(client, "qa1@test.local", "pw") == seed.EXISTS


def test_a_run_of_existing_accounts_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    client = _Client(
        _AuthApiError("A user with this email address has already been registered")
    )
    monkeypatch.setattr(seed, "_service_client", lambda: client)

    assert seed.main(["--batch", "2"]) == 0
    assert "0 created, 2 already existed, 0 failed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Real failures are not swallowed
# ---------------------------------------------------------------------------


def test_a_genuine_error_propagates_out_of_seed_account() -> None:
    """A bad service-role key and a duplicate email arrive as the same exception
    class, so only the duplicate's wording is tolerated. Everything else is a
    real failure and says so."""
    client = _Client(_AuthApiError("Invalid API key", code="unauthorized"))

    with pytest.raises(_AuthApiError):
        seed.seed_account(client, "qa1@test.local", "pw")


def test_main_reports_failures_and_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """One bad account does not abandon the rest of the batch, but the run is
    not a success either."""
    client = _Client(_AuthApiError("Invalid API key", code="unauthorized"))
    monkeypatch.setattr(seed, "_service_client", lambda: client)

    assert seed.main(["--batch", "2"]) == 1

    captured = capsys.readouterr()
    assert len(client.auth.admin.calls) == 2
    assert "0 created, 0 already existed, 2 failed" in captured.out
    assert "Invalid API key" in captured.err
