"""DTO building blocks shared by every dashboard surface.

Lifted out of ``dashboard_schemas`` once a second surface (people) needed them:
a module named for one screen is the wrong home for the base class every screen
inherits.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base DTO: accepts snake_case in Python, emits camelCase on the wire.

    See ``app/domain/dashboard_schemas`` for why ``/auth/*`` does not use this.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Page(CamelModel, Generic[T]):
    """The one list envelope every collection endpoint returns.

    Identical whether or not there is data -- an empty collection is
    ``{"items": [], "total": 0, ...}`` with HTTP 200, never a 404. The dashboard
    has never rendered an empty state (FRONTEND_MEETING_AGENDA.md item 7), so
    giving it exactly one shape to design against is the cheapest help available
    from this side.
    """

    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class MessageResult(CamelModel):
    """Acknowledgement for an action with nothing meaningful to return."""

    message: str
