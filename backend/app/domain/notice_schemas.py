"""DTOs for the notice board."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.common_schemas import CamelModel

#: The urgency vocabulary the Notices screen offers. Stored lowercase.
NOTICE_URGENCIES = ("info", "important", "urgent")

#: Free text rather than an enum: the screen ships a fixed list of categories but
#: an association's notice categories are its own business, and a CHECK constraint
#: on this would turn "add a category" into a migration.
_MAX_CATEGORY = 80


class CreateNoticeRequest(CamelModel):
    """Body for ``POST /notices``.

    Field names follow the frontend's ``addNotice({title, description, category,
    urgency})`` exactly, so the screen needs no payload mapping. ``description``
    is stored in ``notices.body``.
    """

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category: str = Field(default="General", min_length=1, max_length=_MAX_CATEGORY)
    urgency: str = Field(default="Info", min_length=1, max_length=20)


class NoticeCreated(CamelModel):
    """The stored notice, echoed back.

    Mirrors the field names in the shared dashboard snapshot's ``notices[]`` so a
    caller can drop this straight into the same render path -- with two additions,
    ``category`` and ``urgency``, which the snapshot does not yet carry.
    """

    id: str
    title: str
    description: str
    category: str
    urgency: str
    published_at: datetime | None = None
    created_at: datetime
