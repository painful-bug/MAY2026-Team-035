"""The service-operations routers, aggregated into one mountable router.

Same arrangement as ``admin_api.py`` and ``resident_api.py``, for the reason
those give: ``app.api.v1`` mounts this with one import and one
``include_router``, so two workstreams never edit the same router list and the
merge stays clean. Twelve routers, which is all of them.

``complaint_routing`` (0050) sits here for the same ownership reason
``resident_scheduling`` does. A complaint is the resident surface's noun, but
*which department holds it* is a department question end to end -- the queue is
a department's, the transfer request is a supervisor's and the answer is their
manager's -- and separating it from the hiring and work-order routers that share
those populations would put one half of the department's day in a file the other
half's author never opens.

``messages`` (0046) sits here even though its audience is every portal: the
chat dock exists because of this workstream's populations — a manager and
their employee, a worker and the resident whose job they hold — and its guard
posture (identity only, RLS does the scoping) matches this aggregate's.

``worker_jobs`` and ``worker_schedule`` sit beside them and share their prefix
with ``worker_communities``: ``/worker`` is one portal, and splitting it across
aggregates would mean the screen a worker opens is described in three files.

``resident_scheduling`` sits here rather than in ``resident_api.py``, and the
reason is ownership rather than audience: it is the resident-facing end of the
work-order state machine, and the endpoint that answers a proposal has to stay
next to the one that makes it. Splitting them across two aggregates would put
one half of a two-sided conversation in a file the other half's author never
opens.

**This is the first surface whose callers are not scoped to a community.** A
service person registers globally and is hired into communities afterwards, so
most routers here declare identity guards where the other two aggregates declare
membership ones. See ``docs/design/SERVICE_OPERATIONS_DESIGN.md``.

``security_operations`` is the exception and is not an inconsistency: a gate
belongs to one society, so it resolves a community from the caller's membership
like the admin surface does. Same aggregate because it is the same population --
a guard is hired by exactly the machinery that hires a plumber.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    complaint_routing,
    conversations,
    department_hiring,
    messages,
    resident_scheduling,
    security_operations,
    service_providers,
    skills,
    work_orders,
    worker_communities,
    worker_jobs,
    worker_schedule,
)

service_router = APIRouter()
service_router.include_router(service_providers.router)
service_router.include_router(worker_communities.router)
service_router.include_router(worker_jobs.router)
service_router.include_router(worker_schedule.router)
service_router.include_router(department_hiring.router)
service_router.include_router(conversations.router)
service_router.include_router(work_orders.router)
service_router.include_router(resident_scheduling.router)
service_router.include_router(security_operations.router)
service_router.include_router(skills.router)
service_router.include_router(complaint_routing.router)
service_router.include_router(messages.router)
