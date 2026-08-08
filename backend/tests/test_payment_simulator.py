"""The simulated gateway — the outcomes, and the things it must never keep.

Two groups matter more than the rest.

**The failure paths.** They are the reason the simulator exists rather than a
stub that always succeeds: with a real provider in test mode, a decline is a card
you have to go and find, and here it is one expiry date. A demonstration that
cannot be run in front of somebody is not a demonstration.

**The absence of the card.** `SimulatedOutcome` has three fields and none of them
may carry a number, a CVV or an expiry. That is a property no assertion about a
return value catches by accident, so it is asserted directly.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.payment_simulator import SimulatedOutcome, simulate

GOOD_CARD = "4242 4242 4242 4242"
TODAY = date(2026, 8, 4)


def card(number: str = GOOD_CARD, **overrides: object) -> SimulatedOutcome:
    kwargs: dict = {
        "method": "card",
        "card_number": number,
        "card_cvv": "123",
        "expiry_month": 12,
        "expiry_year": 2030,
        "today": TODAY,
    }
    kwargs.update(overrides)
    return simulate(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The happy path, and the worked example the brief asked for
# ---------------------------------------------------------------------------


def test_the_published_test_card_succeeds() -> None:
    outcome = card()

    assert outcome.status == "succeeded"
    assert outcome.succeeded is True
    assert outcome.failure_code is None


def test_the_same_card_with_a_past_expiry_fails() -> None:
    """`PO`'s worked example, and the whole point of a simulator that can be made
    to fail on demand rather than by accident."""
    outcome = card(expiry_month=1, expiry_year=2020)

    assert outcome.status == "failed"
    assert outcome.failure_code == "card_expired"


def test_a_card_is_good_through_the_last_day_of_its_expiry_month() -> None:
    """The off-by-one that would decline a valid card for up to a month."""
    assert card(expiry_month=8, expiry_year=2026).succeeded is True
    assert card(expiry_month=7, expiry_year=2026).failure_code == "card_expired"


@pytest.mark.parametrize(
    ("number", "code"),
    [
        ("4000000000000002", "card_declined"),
        ("4000000000009995", "insufficient_funds"),
        ("4000000000000069", "card_expired"),
    ],
)
def test_each_test_card_declines_with_its_own_reason(number: str, code: str) -> None:
    """Distinct codes, because "declined" and "no money" are different things to
    tell somebody, and the client is the one phrasing it."""
    assert card(number).failure_code == code


def test_the_expiry_rule_wins_over_a_cards_own_verdict() -> None:
    """So the demonstration works on whichever card is to hand, rather than only
    on the one with no other opinion."""
    assert card("4000000000000002", expiry_month=1, expiry_year=2020).failure_code == (
        "card_expired"
    )


def test_a_number_that_is_not_a_test_card_is_refused_before_anything_else() -> None:
    """§11.3, and the argument is not convenience. A simulator that accepted any
    Luhn-valid number is one that will eventually be handed a real card by
    somebody being helpful, and at that moment this is an application holding a
    live PAN with none of the obligations that implies."""
    outcome = card("4111111111111111")

    assert outcome.failure_code == "card_not_supported"


def test_a_refused_number_is_not_echoed_back_even_masked() -> None:
    """Four digits of a number we have just declined to accept is still four
    digits of a number we declined to accept."""
    assert card("4111111111111111").instrument_label == "card"


@pytest.mark.parametrize("cvv", ["12", "12345", "abc", ""])
def test_a_malformed_cvv_is_card_invalid(cvv: str) -> None:
    assert card(card_cvv=cvv).failure_code == "card_invalid"


def test_a_month_that_is_not_a_month_is_card_invalid() -> None:
    assert card(expiry_month=13).failure_code == "card_invalid"


# ---------------------------------------------------------------------------
# UPI — the only method the shipped screen enables
# ---------------------------------------------------------------------------


def test_a_well_formed_vpa_succeeds() -> None:
    outcome = simulate(method="upi", vpa="resident@okhdfcbank")

    assert outcome.succeeded is True
    assert outcome.instrument_label == "resident@okhdfcbank"


@pytest.mark.parametrize("vpa", ["failure@okaxis", "fail@upi", "FAILURE@okaxis"])
def test_the_failure_handles_decline(vpa: str) -> None:
    """The UPI half of the expiry demonstration. `Payments.jsx` enables UPI and
    disables cards, so without this the failure path is unreachable from the only
    payment screen that exists."""
    assert simulate(method="upi", vpa=vpa).failure_code == "payment_declined"


def test_no_vpa_at_all_succeeds_because_the_screen_collects_none() -> None:
    """The shipped modal renders UPI as the single enabled option and its Confirm
    button sends no instrument. Refusing that would mean the endpoint could not
    be called from the screen it was built for."""
    outcome = simulate(method="upi", vpa="")

    assert outcome.succeeded is True
    assert outcome.instrument_label == "UPI"


def test_a_malformed_vpa_is_refused() -> None:
    assert simulate(method="upi", vpa="not-a-vpa").failure_code == "invalid_vpa"


def test_an_unknown_method_fails_rather_than_passing_by_default() -> None:
    """*Passes by default* is about instruments, not about methods nobody built."""
    assert simulate(method="netbanking").failure_code == "method_not_supported"


# ---------------------------------------------------------------------------
# What must never come back out
# ---------------------------------------------------------------------------


def test_no_field_of_the_outcome_carries_the_card() -> None:
    """§11.3. The card is read by this function and discarded inside it; what
    leaves is a receipt line."""
    outcome = card()
    rendered = " ".join(str(value) for value in vars(outcome).values())

    assert "4242424242424242" not in rendered
    assert "123" not in rendered
    assert "2030" not in rendered


def test_the_label_is_the_last_four_and_nothing_more() -> None:
    assert card().instrument_label == "•••• 4242"


def test_the_same_input_always_gives_the_same_answer() -> None:
    """No randomness anywhere. A demo that fails one time in ten is a demo nobody
    can run twice, and a failure you cannot reproduce is one you cannot show."""
    assert {card("4000000000009995").failure_code for _ in range(25)} == {
        "insufficient_funds"
    }
