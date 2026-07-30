"""Notice board service."""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.core.formatting import parse_instant
from app.core.logging import get_logger
from app.domain.notice_schemas import (
    NOTICE_URGENCIES,
    CreateNoticeRequest,
    NoticeCreated,
)
from app.repositories import notices_repository as repo
from supabase import Client

_logger = get_logger(__name__)


def create_notice(
    client: Client,
    *,
    community_id: str,
    membership_id: str,
    body: CreateNoticeRequest,
) -> NoticeCreated:
    """Publish a notice, returning the stored row.

    Raises:
        ValidationError: If ``urgency`` is outside the screen's vocabulary.
    """
    urgency = body.urgency.strip().lower()
    if urgency not in NOTICE_URGENCIES:
        raise ValidationError(
            f"Urgency must be one of: {', '.join(NOTICE_URGENCIES)}.",
        )

    row = repo.insert_notice(
        client,
        community_id=community_id,
        membership_id=membership_id,
        title=body.title.strip(),
        body_text=body.description.strip(),
        category=body.category.strip(),
        urgency=urgency,
    )
    _logger.info(
        "notice.published",
        extra={"notice_id": row["id"], "community_id": community_id},
    )

    return NoticeCreated(
        id=row["id"],
        title=row["title"],
        description=row.get("body") or "",
        category=row.get("category") or body.category.strip(),
        urgency=row.get("urgency") or urgency,
        published_at=(
            parse_instant(row["published_at"]) if row.get("published_at") else None
        ),
        created_at=parse_instant(row["created_at"]),
    )
