"""Translation between stored vocabularies and the strings the frontend renders.

The database stores `in_progress`; the React app renders `In Progress` and puts
that exact string in a `<select>`. Neither can change, so the mapping lives here
-- in one testable place rather than sprinkled through the service layer.

The complaint statuses target the baseline's ``public.complaint_status`` ENUM,
which is a closed set: ``open``, ``acknowledged``, ``in_progress``, ``resolved``,
``closed``, ``cancelled``. Writing anything else is not a bad value that lands in
the row, it is a ``22P02`` from Postgres.

That matters because this table used to map ``Pending -> 'pending'`` and
``Reopened -> 'reopened'``, neither of which is a member of that enum. Those
values came from the pre-baseline schema, where the column was text with a CHECK.
Every ``PATCH /complaints/{id}`` sending either would have failed against a real
database -- the endpoint's tests pass because they never reach one.

Two mappings are deliberately **not** round-trips:

* ``closed`` renders as ``Resolved`` -- the frontend's status select has only
  three options and closed is not one of them.
* ``Reopened`` stores as ``open`` -- which is what reopening means to the
  baseline, and what the frontend itself does: ``reopenComplaint`` sets
  ``status: 'Pending'`` and increments a counter rather than introducing a fourth
  status. The reopen *event* is preserved on the timeline by 0020, so the
  distinction the old ``reopened`` value carried is not lost, only moved to where
  it can be counted.

So ``to_wire(to_storage(x))`` is stable, but ``to_storage(to_wire(x))`` is not.
That asymmetry is the point: the database keeps a distinction the UI does not
show, instead of throwing it away to make a table symmetrical.
"""

from __future__ import annotations

# Values on the right MUST be members of `public.complaint_status`.
_STATUS_TO_STORAGE = {
    "pending": "open",
    "open": "open",
    "acknowledged": "acknowledged",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "closed": "closed",
    "reopened": "open",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}

# A6: the frontend has exactly two department states, Active and Inactive;
# migration 0011's CHECK allows 'active' and 'archived'. Both vocabularies have
# two values, so the mapping is total and lossless in both directions -- unlike
# the complaint statuses above, this one IS a round trip. Whether the column
# should simply say 'inactive' is DECISIONS_NEEDED D5.
_DEPARTMENT_STATUS_TO_WIRE = {"active": "Active", "archived": "Inactive"}

_DEPARTMENT_STATUS_TO_STORAGE = {
    "active": "active",
    "inactive": "archived",
    "archived": "archived",
}

# A15: the Maintenance screen filters on exactly two values, `Paid` and `Unpaid`
# (Maintenance.jsx:92), while an invoice has five lifecycle states. This is NOT a
# round trip and cannot be: `partially_paid` renders as `Unpaid`, because money
# is still owed and the screen's question is "does this flat owe us anything".
#
# `void` is given its own wire value rather than being folded into `Unpaid`. It
# would otherwise be counted as a receivable by any client that sums the rows,
# and a cancelled bill is not money anyone expects to collect.
_INVOICE_STATUS_TO_WIRE = {
    "draft": "Unpaid",
    "issued": "Unpaid",
    "partially_paid": "Unpaid",
    "paid": "Paid",
    "void": "Void",
}

# The frontend writes the method as a display string ('Net Banking', 'Credit
# Card' -- data/payments.js) and renders it verbatim. The database stores the
# ERD's PaymentMethod vocabulary. Both directions are total, so this one IS a
# round trip.
_PAYMENT_METHOD_TO_WIRE = {
    "upi": "UPI",
    "card": "Credit Card",
    "netbanking": "Net Banking",
    "cash": "Cash",
    "cheque": "Cheque",
    "bank_transfer": "Bank Transfer",
}

_PAYMENT_METHOD_TO_STORAGE = {
    "upi": "upi",
    "card": "card",
    "credit card": "card",
    "debit card": "card",
    "netbanking": "netbanking",
    "net banking": "netbanking",
    "cash": "cash",
    "cheque": "cheque",
    "check": "cheque",
    "bank_transfer": "bank_transfer",
    "bank transfer": "bank_transfer",
}

# ---------------------------------------------------------------------------
# Amenities -- the surface that needed the least translation of any so far.
#
# `bookingStatuses.js`, `ledgerStatuses.js`, `bookingTimelineStates.js` and
# `bookingFormOptions.js` all already separate the machine value from its label:
# the frontend stores `pending` and renders `BOOKING_STATUS_LABELS[pending]`.
# So booking status, ledger payment status, booking type and cancellation reason
# codes pass through unchanged, and there is deliberately no mapping table for
# them -- a pass-through table is a place for the two vocabularies to drift.
#
# Only three things actually differ, and they are below.
# ---------------------------------------------------------------------------

# The frontend capitalises the booking mode ('Shared') and uses it as a value,
# not a label -- BOOKING_MODE.SHARED === 'Shared' is compared directly in
# `amenitiesService.js` and `Amenities.jsx`. The column is lowercase because
# every other CHECK vocabulary in the schema is. Total in both directions.
_BOOKING_MODE_TO_WIRE = {
    "shared": "Shared",
    "exclusive": "Exclusive",
    "hybrid": "Hybrid",
}

_BOOKING_MODE_TO_STORAGE = {
    "shared": "shared",
    "exclusive": "exclusive",
    "hybrid": "hybrid",
}

_AMENITY_STATUS_TO_WIRE = {"active": "Active", "inactive": "Inactive"}

# Weekdays are stored as ISO day numbers and rendered as English names. The
# database has to evaluate "is the 14th a closed day?" in SQL, and
# `extract(isodow from ...)` is the only way to ask that without depending on the
# server's locale -- `to_char(d, 'Day')` returns whatever lc_time says, which is
# not something a booking rule should hinge on. The names are the frontend's
# WEEK_DAYS array, Monday-first, which is why ISO numbering lines up exactly.
_WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

_WEEKDAY_TO_NUMBER = {
    name.lower(): index + 1 for index, name in enumerate(_WEEKDAY_NAMES)
}

# ---------------------------------------------------------------------------
# Settings (build step 9)
# ---------------------------------------------------------------------------

# `communities.community_type` stores the frontend's own machine values --
# COMMUNITY_TYPES.APARTMENT === 'apartment' -- so there is nothing to translate
# on the way out. Only the label differs, and it differs in a way no rule can
# derive: `communityTypeOptions` renders 'layout_villa' as 'Layout / Villa',
# spaces, slash and all.
_COMMUNITY_TYPE_LABELS = {
    "apartment": "Apartment",
    "layout_villa": "Layout / Villa",
}

# What a late fine repeats on. The frontend's copy says "a flat Rs.100 weekly
# fine", which names exactly one of these three; the other two exist because a
# monthly fine and a one-off penalty are both things communities do, and adding
# them later would mean a migration for a CHECK constraint.
_LATE_FEE_PERIOD_TO_WIRE = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "once": "One-time",
}

_LATE_FEE_PERIOD_TO_STORAGE = {
    "weekly": "weekly",
    "monthly": "monthly",
    "once": "once",
    "one-time": "once",
    "one time": "once",
    "onetime": "once",
}

# What the backend actually implements for a feature module, straight from
# `module_catalogue.backend_status`. Rendered rather than mapped -- these are our
# own words, because no frontend vocabulary for them exists yet.
_BACKEND_STATUS_TO_WIRE = {
    "implemented": "Implemented",
    "partial": "Partial",
    "none": "Not implemented",
}


def status_to_storage(value: str | None) -> str | None:
    """Frontend status -> the stored value. None when unrecognised."""
    return _STATUS_TO_STORAGE.get((value or "").strip().lower())


def department_status_to_wire(value: str | None) -> str:
    """Stored department status -> the string the frontend renders."""
    return _DEPARTMENT_STATUS_TO_WIRE.get((value or "").lower(), "Active")


def department_status_to_storage(value: str | None) -> str | None:
    """Frontend department status -> the stored value. None when unrecognised."""
    return _DEPARTMENT_STATUS_TO_STORAGE.get((value or "").strip().lower())


def invoice_status_to_wire(value: str | None) -> str:
    """Stored invoice status -> the ``Paid``/``Unpaid``/``Void`` the table shows."""
    return _INVOICE_STATUS_TO_WIRE.get((value or "").lower(), "Unpaid")


def payment_method_to_wire(value: str | None) -> str | None:
    """Stored payment method -> the string the payment history renders."""
    if not value:
        return None
    return _PAYMENT_METHOD_TO_WIRE.get(value.lower(), value)


def payment_method_to_storage(value: str | None) -> str | None:
    """Frontend payment method -> the stored value. None when unrecognised."""
    return _PAYMENT_METHOD_TO_STORAGE.get((value or "").strip().lower())


def booking_mode_to_wire(value: str | None) -> str:
    """Stored booking mode -> the ``Shared``/``Exclusive``/``Hybrid`` the UI
    compares against directly."""
    return _BOOKING_MODE_TO_WIRE.get((value or "").lower(), "Shared")


def booking_mode_to_storage(value: str | None) -> str | None:
    """Frontend booking mode -> the stored value. None when unrecognised."""
    return _BOOKING_MODE_TO_STORAGE.get((value or "").strip().lower())


def amenity_status_to_wire(value: str | None) -> str:
    """Stored amenity status -> the ``Active``/``Inactive`` badge on the card."""
    return _AMENITY_STATUS_TO_WIRE.get((value or "").lower(), "Inactive")


def weekday_to_wire(value: int | None) -> str | None:
    """ISO day number -> ``Monday``. None for anything outside 1-7."""
    if value is None or not 1 <= int(value) <= 7:
        return None
    return _WEEKDAY_NAMES[int(value) - 1]


def weekday_to_storage(value: str | int | None) -> int | None:
    """``Monday`` or ``1`` -> the ISO day number. None when unrecognised.

    Accepts a number as well as a name so that a client which has already learnt
    the stored form is not forced back through the display form to talk to us.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 7 else None
    text = str(value).strip()
    if text.isdigit():
        number = int(text)
        return number if 1 <= number <= 7 else None
    return _WEEKDAY_TO_NUMBER.get(text.lower())


def weekdays_to_wire(values: list[int] | None) -> list[str]:
    """A stored ``closed_days`` array -> the names the settings form checkboxes use."""
    names = [weekday_to_wire(value) for value in (values or [])]
    return [name for name in names if name is not None]


def weekdays_to_storage(values: list[str | int] | None) -> list[int]:
    """The settings form's day names -> stored ISO numbers, sorted and deduplicated.

    Unrecognised entries are dropped rather than stored: a CHECK constraint
    rejects the whole array for one bad element, which would turn a typo in one
    checkbox into a failed save of all thirty settings.
    """
    numbers = {weekday_to_storage(value) for value in (values or [])}
    return sorted(number for number in numbers if number is not None)


def community_type_label(value: str | None) -> str:
    """Stored community type -> the label the onboarding select renders."""
    key = (value or "").lower()
    return _COMMUNITY_TYPE_LABELS.get(key, "Apartment")


def late_fee_period_to_wire(value: str | None) -> str:
    """Stored fine period -> the label a settings form shows."""
    return _LATE_FEE_PERIOD_TO_WIRE.get((value or "").lower(), "Weekly")


def late_fee_period_to_storage(value: str | None) -> str | None:
    """A fine period from the wire -> the stored value, or None if unrecognised."""
    if value is None:
        return None
    return _LATE_FEE_PERIOD_TO_STORAGE.get(value.strip().lower())


def backend_status_to_wire(value: str | None) -> str:
    """``module_catalogue.backend_status`` -> a phrase for a settings screen."""
    return _BACKEND_STATUS_TO_WIRE.get((value or "").lower(), "Not implemented")
