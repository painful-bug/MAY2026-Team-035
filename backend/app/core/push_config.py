"""VAPID configuration, read from the environment and never from a database.

Web Push needs three values: ``VAPID_PUBLIC_KEY``, ``VAPID_PRIVATE_KEY`` and
``VAPID_SUBJECT``. See ``docs/design/RESIDENT_BACKEND_DESIGN.md`` §10.5 for the
full argument; the two things worth repeating here are why this is a second
settings class and why the environment is the right place.

**Why a second class.** ``app/config.py`` belongs to the auth workstream and this
one does not edit it. ``pydantic-settings`` makes that free rather than awkward:
a second ``BaseSettings`` with the same ``model_config`` reads the same ``.env``,
ignores everything that is not its own, and inherits the existing gitignore, the
``.env.example`` habit and the deploy story with no coordination at all. If the
auth owner would rather these three live in the central ``Settings``, moving them
is a two-line change.

**Why the environment.** The instinct is to reach for something stronger than a
``.env`` file. The reason not to is that the environment is *already* this
application's trust root and it holds something strictly more dangerous:
``SUPABASE_SERVICE_ROLE_KEY`` bypasses row-level security on every table in the
project, while the VAPID private key signs a JWT that lets us push to endpoints
an attacker would have to steal separately, from a table that is ``service_role``
only. Putting the weaker secret behind a stronger mechanism while the stronger
one stays in ``.env`` adds a moving part and a second failure mode, and reduces
nothing.

**Fail closed, quietly.** Missing or malformed values mean ``enabled`` is false:
the sender never starts, the two push endpoints return ``503``
``push_not_configured``, and *everything else in the product works normally*.
Push is an enhancement, so an unconfigured environment must not be a broken
environment -- the same shape as ``0024`` scheduling under ``pg_cron`` when the
extension is present and no-opping when it is not.

**This workstream never generates or sees a real key.**
``scripts/generate_vapid_keys.py`` prints three lines to stdout and writes no
file; it is run by whoever already holds that environment's service-role key.
"""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# base64url, unpadded, single line -- exactly what `py-vapid`, `pywebpush` and
# the browser's `applicationServerKey` all want. A PEM in an environment
# variable needs newline escaping, and escaped newlines are how a key gets
# corrupted in a CI secret store at 2am.
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")

# The raw P-256 keys, base64url-encoded: a 32-byte private scalar and a 65-byte
# uncompressed public point. Length is checked as a floor rather than an exact
# value because encoders differ on padding; the point is to reject a truncated
# paste, not to re-implement the key format.
_MIN_PRIVATE_KEY_CHARS = 40
_MIN_PUBLIC_KEY_CHARS = 80


class PushSettings(BaseSettings):
    """The VAPID keypair and the contact subject that identifies us to relays."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Defaults are empty rather than required. A backend that refuses to start
    # because nobody has generated a push keypair yet would make an enhancement
    # into a hard dependency, which is the opposite of the decision in 10.5.
    vapid_public_key: str = Field("", alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str = Field("", alias="VAPID_PRIVATE_KEY")
    # `mailto:` or `https:`. RFC 8292 asks for a way to contact the sender; push
    # services use it when something is wrong with our requests.
    vapid_subject: str = Field("", alias="VAPID_SUBJECT")

    @property
    def enabled(self) -> bool:
        """Whether push can actually be sent.

        Checked at startup so the answer is known before a resident subscribes,
        rather than discovered on the first send -- a browser that has been
        allowed to subscribe against a key we cannot sign with is a browser that
        silently never receives anything.
        """
        return not self.configuration_problem()

    def configuration_problem(self) -> str | None:
        """What is wrong with the configuration, or ``None`` if nothing is.

        Returns prose for a log line, never for a response body. The endpoints
        answer ``push_not_configured`` and no more: which of the three values is
        missing is an operator's business and a caller cannot act on it.
        """
        if not (self.vapid_public_key and self.vapid_private_key):
            return "VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are not both set"
        if not self.vapid_subject:
            return "VAPID_SUBJECT is not set"
        if not self.vapid_subject.startswith(("mailto:", "https://")):
            return "VAPID_SUBJECT must be a mailto: or https:// URI"
        for label, value, minimum in (
            ("VAPID_PUBLIC_KEY", self.vapid_public_key, _MIN_PUBLIC_KEY_CHARS),
            ("VAPID_PRIVATE_KEY", self.vapid_private_key, _MIN_PRIVATE_KEY_CHARS),
        ):
            if not _BASE64URL.match(value):
                # Deliberately does not echo the value. This function's return
                # is logged, and half a private key in a log file is a leaked
                # private key.
                return f"{label} is not unpadded base64url on a single line"
            if len(value) < minimum:
                return f"{label} is too short to be a P-256 key"
        return None


@lru_cache
def get_push_settings() -> PushSettings:
    """Return the cached push settings."""
    return PushSettings()  # type: ignore[call-arg]  # values come from the environment
