"""The simulated payment gateway. One pure function, and the seam.

`RESIDENT_BACKEND_DESIGN.md` §11. The brief (`PO`, 2026-08-04) was a gateway we
build, where nothing moves and any payment passes by default, with a few
deliberate failures -- a card past its expiry being the worked example -- *"so
that we can show we handle that too, and maintain business logic for this."*

**That last clause is the whole design.** The point is not a fake success screen.
It is that every path a real gateway produces gets exercised end to end, so that
swapping in a real one changes this module and nothing else.

Three properties, and each one is load-bearing:

**Pure.** No database, no network, no clock beyond comparing an expiry to today.
Everything that touches a row happens in the RPC this feeds, which is why that
RPC takes an outcome and never decides one -- and why it will not change when a
real provider replaces this file.

**Deterministic.** No randomness anywhere. A demo that fails one time in ten is a
demo nobody can run twice, and a failure you cannot reproduce is a failure you
cannot show anyone.

**Forgetful.** The card number, the CVV and the expiry are read by
:func:`simulate` and never leave it. What comes out is a masked label -- `•••• 4242`
-- and an outcome. §11.3: nothing here is stored, logged, echoed in an error, or
written to `payment_events`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

#: The published Stripe test numbers, and *only* these.
#:
#: The argument for a whitelist rather than a Luhn check is §11.3 and it is worth
#: keeping next to the list. A simulated gateway that accepts any Luhn-valid
#: number is a system that **will** be handed a real card -- by a tester being
#: thorough, by someone in a demo audience being helpful, by a marker trying the
#: app the way a resident would. At that moment this is an application holding a
#: live PAN with none of the obligations discharged that holding one implies.
#: Restricting the input closes that by construction, which is worth more than a
#: warning banner nobody reads.
#:
#: Stripe's sandbox can accept anything because Stripe is PCI-DSS certified
#: infrastructure whose business is holding card data safely. Copying the
#: affordance without the substrate is the mistake.
_TEST_CARDS: dict[str, str | None] = {
    "4242424242424242": None,  # the happy path
    "4000000000000002": "card_declined",
    "4000000000009995": "insufficient_funds",
    "4000000000000069": "card_expired",  # declines whatever the expiry says
}

_DIGITS = re.compile(r"\D")
#: `name@handle`, the shape a UPI VPA has. Deliberately loose on the local part:
#: handles proliferate and a regex that knows them all is a regex that rejects a
#: real bank the week after it is written.
_VPA = re.compile(r"^[a-zA-Z0-9._-]{2,64}@[a-zA-Z][a-zA-Z0-9.-]{1,32}$")

#: A VPA whose local part begins this way always declines. It is the UPI half of
#: the expiry-date demonstration -- the frontend enables UPI and nothing else
#: (`Payments.jsx`), so without it the failure path is unreachable from the only
#: screen that exists.
_FAILING_VPA_PREFIXES = ("failure", "fail")


@dataclass(frozen=True)
class SimulatedOutcome:
    """What the gateway decided, and the one string safe to keep.

    ``failure_code`` is a stable identifier and never prose -- ``card_declined``,
    not *"Your card was declined."* The wording is the client's, and so is its
    translation.
    """

    status: str
    failure_code: str | None
    instrument_label: str

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


def _mask_card(digits: str) -> str:
    return f"•••• {digits[-4:]}"


def _expired(expiry_month: int, expiry_year: int, today: date) -> bool:
    """A card is good through the last day of its expiry month."""
    return (expiry_year, expiry_month) < (today.year, today.month)


def _simulate_card(
    *,
    number: str,
    expiry_month: int | None,
    expiry_year: int | None,
    cvv: str,
    today: date,
) -> SimulatedOutcome:
    digits = _DIGITS.sub("", number)
    label = _mask_card(digits) if len(digits) >= 4 else "card"

    if digits not in _TEST_CARDS:
        # Rejected before the simulator evaluates anything, and the label is
        # deliberately generic: echoing back four digits of a number we have just
        # refused to accept would be storing a fragment of the thing we declined
        # to hold.
        return SimulatedOutcome("failed", "card_not_supported", "card")

    if (
        len(cvv) != 3
        or not cvv.isdigit()
        or expiry_month is None
        or expiry_year is None
        or not 1 <= expiry_month <= 12
    ):
        return SimulatedOutcome("failed", "card_invalid", label)

    # Checked before the per-card code, so the worked example wins on every test
    # card rather than only on the one that has no other verdict.
    if _expired(expiry_month, expiry_year, today):
        return SimulatedOutcome("failed", "card_expired", label)

    failure = _TEST_CARDS[digits]
    if failure is not None:
        return SimulatedOutcome("failed", failure, label)
    return SimulatedOutcome("succeeded", None, label)


def _simulate_upi(*, vpa: str) -> SimulatedOutcome:
    handle = vpa.strip()

    if not handle:
        # The only path the resident's screen can currently take. `Payments.jsx`
        # renders UPI as the single enabled option and collects nothing at all --
        # its Confirm button sends a method and no instrument. Treating that as a
        # well-formed UPI payment is what keeps the shipped screen callable; the
        # label says exactly what was known, which was nothing but the method.
        return SimulatedOutcome("succeeded", None, "UPI")

    if not _VPA.match(handle):
        return SimulatedOutcome("failed", "invalid_vpa", "UPI")

    local = handle.split("@", 1)[0].casefold()
    if local.startswith(_FAILING_VPA_PREFIXES):
        return SimulatedOutcome("failed", "payment_declined", handle)

    return SimulatedOutcome("succeeded", None, handle)


def simulate(
    *,
    method: str,
    card_number: str = "",
    card_cvv: str = "",
    expiry_month: int | None = None,
    expiry_year: int | None = None,
    vpa: str = "",
    today: date | None = None,
) -> SimulatedOutcome:
    """Decide an outcome. Reads the instrument; returns nothing that identifies it.

    ``today`` is injectable so the expiry rule can be tested without a card that
    expires while the suite is running -- which is the same reason it is the only
    clock this module has.
    """
    if method == "card":
        return _simulate_card(
            number=card_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            cvv=card_cvv,
            today=today or date.today(),
        )
    if method == "upi":
        return _simulate_upi(vpa=vpa)
    return SimulatedOutcome("failed", "method_not_supported", method or "unknown")
