"""Wire models for the address-lookup proxy.

Deliberately **not** the upstream's payload. Nominatim answers with about thirty
fields per result -- OSM ids, bounding boxes, licence strings, place ranks -- and
none of them are ours to publish or to keep stable. The three facts a location
picker needs are a label a person recognises, and the two numbers that place a
pin, so those are the three fields that cross this boundary.

The label is coarse on purpose. It is stored as ``location_label`` on
``service_providers`` and ``communities`` and is shown on hiring candidate cards,
where the precise coordinate is deliberately withheld -- "Andheri West, Mumbai"
answers *where roughly*, which is the question a hiring manager has, without
answering *which building*, which is nobody's.
"""

from __future__ import annotations

from app.domain.common_schemas import CamelModel

#: The stored column is ``text`` with a 120-character check, and every label this
#: API emits is truncated to it. A label that cannot be saved is not a label.
LOCATION_LABEL_MAX_LENGTH = 120


class GeoPlace(CamelModel):
    """One place: what to call it, and where it is.

    ``label`` is the short form -- three address parts at most -- and is what the
    picker writes into the editable label field. ``description`` is the
    upstream's own full line, kept because a pick-list of five results needs
    enough to tell two "Andheri West" entries apart, and the short label by
    itself does not.
    """

    label: str
    description: str
    latitude: float
    longitude: float
