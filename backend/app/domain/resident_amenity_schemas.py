"""The resident's view of the amenity catalogue.

Separate from ``amenity_schemas.AmenitySummary`` on purpose, and the reason is
the rule in ``docs/design/RESIDENT_BACKEND_DESIGN.md`` 5.1: **role is a
property of the projection, not a filter bolted onto one shared payload.**

``AmenitySummary`` is the admin card. It carries ``pendingRequests`` and
``outstandingDues`` -- how many neighbours are waiting on this hall and how much
money the community is still owed against it. Those are operational figures
about everyone, and a resident deciding whether to book the hall on Saturday has
no business receiving them.

Reusing that model and clearing two fields for residents would work exactly
until someone adds a third field to the admin card, which is the failure mode
5.1 describes: a payload whose safety depends on remembering. Two models means
the resident response cannot grow an admin field by accident, because there is
no line of code that would put one there.

The fields below are the ones that answer *"can I book this, when, and what
will it cost me"*. Everything else on the table -- maintenance notes and
intervals, auto-block settings, the row version, the waitlist flag whose
endpoint does not exist -- is either internal operations or a promise this
backend cannot keep yet.
"""

from __future__ import annotations

from app.domain.common_schemas import CamelModel


class BookableAmenity(CamelModel):
    """One amenity a resident is allowed to request a booking against.

    Every amenity in this response is active and not under a temporary closure,
    so there is no ``status`` field: the filter *is* the meaning, and a
    ``status`` that reads ``Active`` on every row would be noise the client has
    to ignore.

    ``openingTime`` and ``closingTime`` are ``HH:MM`` wall-clock strings in the
    community's own time, not instants -- an opening hour has no timezone to be
    converted from. They are deliberately **not** accompanied by the composed
    ``'6:00 AM - 10:00 PM'`` display string the admin card carries: that is a
    formatting decision, it belongs to whoever is rendering, and duplicating the
    admin service's private formatter here would give one string two sources.
    """

    id: str
    name: str
    description: str
    category: str
    location: str
    image: str
    capacity: int | None = None

    #: ``Shared`` | ``Exclusive`` | ``Hybrid``.
    booking_mode: str
    #: Whether a request lands as pending rather than confirmed. Surfaced so the
    #: booking form can say so before submitting, instead of the resident
    #: discovering it from the status afterwards.
    requires_approval: bool

    opening_time: str
    closing_time: str
    slot_duration_minutes: int

    #: The limits the booking form has to respect. ``None`` means the amenity
    #: sets no limit of its own -- not that there is no limit at all, since the
    #: booking RPC still applies conflict and capacity rules on write.
    minimum_booking_duration_minutes: int | None = None
    maximum_booking_duration_minutes: int | None = None
    advance_booking_window_days: int | None = None
    max_active_bookings_per_resident: int | None = None

    #: Weekday names this amenity is never bookable on, e.g. ``["Sunday"]``.
    closed_days: list[str]

    allow_private_booking: bool
    allow_guest_booking: bool
    allow_recurring_booking: bool
    allow_same_day_booking: bool

    #: What booking costs. The deposit is returnable and the fee is not, so they
    #: are two fields rather than a total -- a resident shown one number cannot
    #: tell how much of it is coming back.
    booking_fee: float
    security_deposit: float
    currency_code: str
    refund_policy: str
