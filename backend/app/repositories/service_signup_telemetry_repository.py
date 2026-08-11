"""Best-effort persistence for the privacy-minimal signup funnel."""

from uuid import UUID

from app.core.supabase_client import get_service_client


def record(visitor_id: UUID, event_name: str) -> None:
    """Store an allowlisted event; telemetry may never interrupt signup."""
    try:
        get_service_client().rpc(
            "record_service_signup_funnel_event",
            {"p_visitor_id": str(visitor_id), "p_event_name": event_name},
        ).execute()
    except Exception:  # noqa: BLE001
        pass
