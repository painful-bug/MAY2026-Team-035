"""Admin dashboard service: composes the read-only surfaces.

This layer is where the frontend's exact display shapes are assembled -- relative
times, flat labels, role labels. Keeping it here rather than in Postgres views is
the whole reason the FastAPI service earns its place: a view would have to push
display concerns into the schema to do the same job.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.formatting import day_ago, long_date, parse_instant
from app.domain.dashboard_schemas import (
    AdminDashboard,
    CollectionSummary,
    CommunitySummary,
    NoticeSummary,
    Page,
    ResidentSummary,
)
from app.domain.roles import display_role
from app.repositories import dashboard_repository as repo
from app.repositories import money_repository
from supabase import Client


def get_community(client: Client, user_id: str) -> CommunitySummary:
    """Return the caller's community."""
    community_id = repo.get_caller_community_id(client, user_id)
    row = repo.get_community(client, community_id)
    return CommunitySummary(
        id=row["id"],
        name=row["name"],
        community_type=row.get("community_type", "apartment"),
        status=row.get("status", "Active"),
        created_at=row["created_at"],
    )


def get_admin_dashboard(client: Client, user_id: str) -> AdminDashboard:
    """Compose the admin home aggregate.

    ``pendingRequests`` became real in build step 4; ``collection`` became real
    in step 7 and is no longer a placeholder.

    The tile reports **whole rupees**, matching the frontend's own rounding, and
    is read from the same database aggregate that serves
    ``GET /invoices/summary`` -- so the home page and the collections screen
    cannot disagree about how much has been collected. ``target`` is everything
    billed, including what is not yet due; ``current`` is what has actually been
    received. A founding community has no invoices at all and reports zeros
    rather than dividing by zero (FRONTEND_MEETING_AGENDA.md item 7).
    """
    community_id = repo.get_caller_community_id(client, user_id)
    money = money_repository.fetch_collection_summary(client, community_id) or {}

    current = round(float(money.get("total_collected") or 0))
    target = round(float(money.get("total_billed") or 0))

    return AdminDashboard(
        total_residents=repo.count_residents(client, community_id),
        pending_requests=repo.count_pending_registrations(client, community_id),
        active_complaints=repo.count_active_complaints(client, community_id),
        collection=CollectionSummary(
            current=current,
            target=target,
            percent=round(current / target * 100) if target > 0 else 0,
        ),
        generated_at=datetime.now(timezone.utc),
    )


def list_residents(
    client: Client,
    user_id: str,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[ResidentSummary]:
    """Page through the community's residents."""
    community_id = repo.get_caller_community_id(client, user_id)
    offset = (page - 1) * page_size

    rows, total = repo.list_residents(
        client, community_id, search=search, offset=offset, limit=page_size
    )

    # One lookup for the whole page rather than one per row (R23 label + id).
    codes = sorted(
        {
            code
            for row in rows
            if (code := (row.get("profiles") or {}).get("apartment_id"))
        }
    )
    code_to_id = repo.map_unit_codes_to_ids(client, community_id, codes)

    items = []
    for row in rows:
        profile = row.get("profiles") or {}
        flat = profile.get("apartment_id")
        items.append(
            ResidentSummary(
                id=row["id"],
                profile_id=row["profile_id"],
                name=profile.get("full_name"),
                # Real as of migration 0012, which adds profiles.email and
                # backfills it from auth.users.
                email=profile.get("email"),
                phone=profile.get("phone"),
                role=row["role"],
                display_role=display_role(row["role"]),
                flat=flat,
                unit_id=code_to_id.get(flat) if flat else None,
                status=row.get("status", "active"),
                joined_at=row["joined_at"],
            )
        )

    return Page[ResidentSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(items) < total,
    )


def list_notices(
    client: Client, user_id: str, *, page: int = 1, page_size: int = 20
) -> Page[NoticeSummary]:
    """Page through published notices, newest first."""
    community_id = repo.get_caller_community_id(client, user_id)
    offset = (page - 1) * page_size

    rows, total = repo.list_notices(
        client, community_id, offset=offset, limit=page_size
    )

    items = [
        NoticeSummary(
            id=row["id"],
            title=row["title"],
            description=row.get("body"),
            category=row.get("category"),
            urgency=row.get("urgency", "info"),
            # Formatted and raw, side by side -- see app.core.formatting.
            date=long_date(parse_instant(row["published_at"])),
            time_ago=day_ago(parse_instant(row["published_at"])),
            published_at=parse_instant(row["published_at"]),
        )
        for row in rows
    ]

    return Page[NoticeSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=offset + len(items) < total,
    )

