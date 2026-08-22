"""Real-JWT coverage for the repaired Complaint Engine v2 database flow."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from supabase import Client, create_client

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_INTEGRATION") != "1",
    reason="requires the local Supabase stack",
)


def _user(service: Client, url: str, anon_key: str, label: str) -> tuple[Client, str]:
    suffix = uuid4().hex
    email = f"{label}-{suffix}@example.test"
    password = f"HomeBandhu-{suffix}-Password!"
    user_id = str(
        service.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        ).user.id
    )
    # Current main creates this row from the auth-user trigger. Upsert keeps the
    # test compatible with both that path and older local stacks.
    service.table("profiles").upsert(
        {"id": user_id, "full_name": label.title(), "display_email": email}
    ).execute()
    client = create_client(url, anon_key)
    client.auth.sign_in_with_password({"email": email, "password": password})
    return client, user_id


def _status(service: Client, complaint_id: str) -> str:
    return str(
        service.table("complaints")
        .select("status")
        .eq("id", complaint_id)
        .single()
        .execute()
        .data["status"]
    )


def test_complaint_engine_v2_real_jwt_rpcs_and_triggers() -> None:
    url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    service = create_client(url, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    resident, resident_profile = _user(service, url, anon_key, "resident")
    other_resident, other_resident_profile = _user(
        service, url, anon_key, "other-resident"
    )
    manager, manager_profile = _user(service, url, anon_key, "manager")
    supervisor, supervisor_profile = _user(service, url, anon_key, "supervisor")
    admin, admin_profile = _user(service, url, anon_key, "admin")
    worker_a, worker_a_profile = _user(service, url, anon_key, "worker-a")
    worker_b, worker_b_profile = _user(service, url, anon_key, "worker-b")
    outside_manager, outside_manager_profile = _user(
        service, url, anon_key, "outside-manager"
    )

    suffix = uuid4().hex
    community_id, other_community_id = str(uuid4()), str(uuid4())
    department_id, alternate_department_id, other_department_id = (
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
    )
    service.table("communities").insert(
        [
            {
                "id": community_id,
                "name": f"V2 Community {suffix}",
                "community_type": "apartment",
                "address_line1": "1 Test Road",
                "city": "Kolkata",
                "state": "West Bengal",
                "postal_code": "700001",
                "latitude": 22.572645,
                "longitude": 88.363892,
            },
            {
                "id": other_community_id,
                "name": f"Other Community {suffix}",
                "community_type": "apartment",
                "address_line1": "2 Test Road",
                "city": "Kolkata",
                "state": "West Bengal",
                "postal_code": "700002",
                "latitude": 22.572645,
                "longitude": 88.363892,
            },
        ]
    ).execute()
    service.table("departments").insert(
        [
            {
                "id": department_id,
                "community_id": community_id,
                "name": "Maintenance",
                "kind": "service",
            },
            {
                "id": alternate_department_id,
                "community_id": community_id,
                "name": "Facilities",
                "kind": "service",
            },
            {
                "id": other_department_id,
                "community_id": other_community_id,
                "name": "Other",
                "kind": "service",
            },
        ]
    ).execute()
    skill_id = str(
        service.table("skills")
        .select("id")
        .eq("name", "Plumbing")
        .single()
        .execute()
        .data["id"]
    )
    service.table("department_skills").insert(
        {"department_id": department_id, "skill_id": skill_id}
    ).execute()

    memberships = (
        service.table("community_memberships")
        .insert(
            [
                {
                    "community_id": community_id,
                    "profile_id": resident_profile,
                    "role": "resident",
                    "status": "active",
                },
                {
                    "community_id": community_id,
                    "profile_id": other_resident_profile,
                    "role": "resident",
                    "status": "active",
                },
                {
                    "community_id": community_id,
                    "profile_id": manager_profile,
                    "department_id": department_id,
                    "role": "manager",
                    "status": "active",
                },
                {
                    "community_id": community_id,
                    "profile_id": supervisor_profile,
                    "department_id": department_id,
                    "role": "worker",
                    "status": "active",
                },
                {
                    "community_id": community_id,
                    "profile_id": admin_profile,
                    "role": "admin",
                    "status": "active",
                },
                {
                    "community_id": community_id,
                    "profile_id": worker_a_profile,
                    "department_id": department_id,
                    "role": "worker",
                    "status": "active",
                },
                {
                    "community_id": community_id,
                    "profile_id": worker_b_profile,
                    "department_id": department_id,
                    "role": "worker",
                    "status": "active",
                },
                {
                    "community_id": other_community_id,
                    "profile_id": outside_manager_profile,
                    "department_id": other_department_id,
                    "role": "manager",
                    "status": "active",
                },
            ]
        )
        .execute()
        .data
    )
    membership_by_profile = {row["profile_id"]: row["id"] for row in memberships}
    workers = (
        service.table("staff_assignments")
        .insert(
            [
                {
                    "community_id": community_id,
                    "department_id": department_id,
                    "membership_id": membership_by_profile[supervisor_profile],
                    "display_name": "Supervisor",
                    "rank": "supervisor",
                    "status": "active",
                    "employment_type": "staff",
                },
                {
                    "community_id": community_id,
                    "department_id": department_id,
                    "membership_id": membership_by_profile[worker_a_profile],
                    "display_name": "Worker A",
                    "rank": "member",
                    "status": "active",
                    "employment_type": "staff",
                },
                {
                    "community_id": community_id,
                    "department_id": department_id,
                    "membership_id": membership_by_profile[worker_b_profile],
                    "display_name": "Worker B",
                    "rank": "member",
                    "status": "active",
                    "employment_type": "staff",
                },
            ]
        )
        .execute()
        .data
    )
    staff_by_membership = {row["membership_id"]: row["id"] for row in workers}
    supervisor_staff = staff_by_membership[membership_by_profile[supervisor_profile]]
    worker_a_staff = staff_by_membership[membership_by_profile[worker_a_profile]]
    worker_b_staff = staff_by_membership[membership_by_profile[worker_b_profile]]

    def raise_complaint(title: str, priority: str = "low") -> str:
        return str(
            resident.rpc(
                "raise_complaint",
                {
                    "p_membership_id": membership_by_profile[resident_profile],
                    "p_title": title,
                    "p_description": "Leaking fixture",
                    "p_category": None,
                    "p_priority": priority,
                    "p_location": "A-101",
                    "p_department_id": None,
                    "p_skill_id": skill_id,
                },
            )
            .execute()
            .data
        )

    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)

    def create_job(actor: Client, complaint_id: str, day: int) -> str:
        return str(
            actor.rpc(
                "create_work_order",
                {
                    "p_complaint_id": complaint_id,
                    "p_department_id": None,
                    "p_skill_id": skill_id,
                    "p_subject_kind": "facility",
                    "p_location_text": "A-101",
                    "p_scheduled_start_at": (start + timedelta(days=day)).isoformat(),
                    "p_scheduled_end_at": (
                        start + timedelta(days=day, hours=1)
                    ).isoformat(),
                    "p_note": None,
                },
            )
            .execute()
            .data
        )

    complaint_id = raise_complaint("Kitchen leak")
    routed = (
        service.table("complaints")
        .select("department_id,category")
        .eq("id", complaint_id)
        .single()
        .execute()
        .data
    )
    assert routed == {"department_id": department_id, "category": "Plumbing"}
    service.table("department_skills").insert(
        {"department_id": alternate_department_id, "skill_id": skill_id}
    ).execute()
    assert (
        resident.rpc(
            "resolve_complaint_department",
            {
                "p_community_id": community_id,
                "p_category": "",
                "p_department_id": None,
                "p_skill_id": skill_id,
            },
        )
        .execute()
        .data
        is None
    )
    service.table("department_skills").delete().eq(
        "department_id", alternate_department_id
    ).execute()

    # The assignment trigger projects `open` to `acknowledged`; work-order
    # updates then project in-progress and resolved states.
    job_one = create_job(manager, complaint_id, 1)
    offer_id = (
        manager.rpc(
            "assign_work_order",
            {
                "p_work_order_id": job_one,
                "p_staff_assignment_id": worker_a_staff,
                "p_scheduled_start_at": None,
                "p_scheduled_end_at": None,
            },
        )
        .execute()
        .data
    )
    assert offer_id and _status(service, complaint_id) == "acknowledged"
    worker_a.rpc("accept_work_order_offer", {"p_work_order_id": job_one}).execute()
    assert (
        service.table("dm_threads")
        .select("id")
        .eq("work_order_id", job_one)
        .execute()
        .data
    )
    worker_a.rpc("start_work_order", {"p_work_order_id": job_one}).execute()
    assert _status(service, complaint_id) == "in_progress"

    job_two = create_job(admin, complaint_id, 2)
    admin.rpc(
        "assign_work_order",
        {
            "p_work_order_id": job_two,
            "p_staff_assignment_id": worker_b_staff,
            "p_scheduled_start_at": None,
            "p_scheduled_end_at": None,
        },
    ).execute()
    worker_b.rpc("accept_work_order_offer", {"p_work_order_id": job_two}).execute()
    worker_a.rpc(
        "complete_work_order", {"p_work_order_id": job_one, "p_notes": "Fixed"}
    ).execute()
    assert _status(service, complaint_id) == "in_progress"
    worker_b.rpc(
        "complete_work_order",
        {"p_work_order_id": job_two, "p_notes": "Checked"},
    ).execute()
    assert _status(service, complaint_id) == "resolved"
    task_kinds = {
        row["kind"]
        for row in service.table("dispatch_tasks")
        .select("kind")
        .eq("complaint_id", complaint_id)
        .execute()
        .data
    }
    assert task_kinds >= {"auto_close_warning", "auto_close"}
    assert (
        service.rpc(
            "dispatch_auto_close",
            {"p_complaint_id": complaint_id, "p_warn": True},
        )
        .execute()
        .data
        is True
    )
    assert (
        service.rpc(
            "dispatch_auto_close",
            {"p_complaint_id": complaint_id, "p_warn": False},
        )
        .execute()
        .data
        is True
    )
    assert _status(service, complaint_id) == "closed"
    event_types = {
        row["event_type"]
        for row in service.table("complaint_events")
        .select("event_type")
        .eq("complaint_id", complaint_id)
        .execute()
        .data
    }
    assert event_types >= {"auto_close_warning", "auto_closed"}
    with pytest.raises(APIError):
        create_job(manager, complaint_id, 3)

    # Tenant and role checks remain intact around the repaired internals.
    move_complaint = raise_complaint("Move guard")
    move_job = create_job(supervisor, move_complaint, 4)
    with pytest.raises(APIError):
        service.table("complaints").update(
            {"department_id": alternate_department_id}
        ).eq("id", move_complaint).execute()
    with pytest.raises(APIError):
        worker_a.rpc(
            "assign_work_order",
            {
                "p_work_order_id": move_job,
                "p_staff_assignment_id": worker_a_staff,
                "p_scheduled_start_at": None,
                "p_scheduled_end_at": None,
            },
        ).execute()
    with pytest.raises(APIError):
        outside_manager.rpc(
            "create_work_order",
            {
                "p_complaint_id": move_complaint,
                "p_department_id": None,
                "p_skill_id": skill_id,
                "p_subject_kind": "facility",
                "p_location_text": None,
                "p_scheduled_start_at": None,
                "p_scheduled_end_at": None,
                "p_note": None,
            },
        ).execute()

    # Ordinary candidates exclude a decline. The explicit supervisor view can
    # show that worker as excluded, while a critical fallback can override the
    # decline without bypassing availability checks.
    decline_complaint = raise_complaint("Declined offer")
    decline_job = create_job(manager, decline_complaint, 5)
    manager.rpc(
        "assign_work_order",
        {
            "p_work_order_id": decline_job,
            "p_staff_assignment_id": worker_a_staff,
            "p_scheduled_start_at": None,
            "p_scheduled_end_at": None,
        },
    ).execute()
    worker_a.rpc(
        "decline_work_order_offer",
        {"p_work_order_id": decline_job, "p_reason": "Unavailable"},
    ).execute()
    ordinary = (
        manager.rpc(
            "work_order_candidates",
            {"p_work_order_id": decline_job, "p_include_excluded": False},
        )
        .execute()
        .data
    )
    all_candidates = (
        manager.rpc(
            "work_order_candidates",
            {"p_work_order_id": decline_job, "p_include_excluded": True},
        )
        .execute()
        .data
    )
    assert worker_a_staff not in {row["staff_assignment_id"] for row in ordinary}
    declined_candidate = next(
        row for row in all_candidates if row["staff_assignment_id"] == worker_a_staff
    )
    assert declined_candidate["excluded"] is True

    service.table("worker_unavailability").insert(
        [
            {
                "staff_assignment_id": worker_b_staff,
                "starts_at": (start + timedelta(days=6)).isoformat(),
                "ends_at": (start + timedelta(days=8)).isoformat(),
                "reason": "Leave",
            },
            {
                "staff_assignment_id": supervisor_staff,
                "starts_at": (start + timedelta(days=6)).isoformat(),
                "ends_at": (start + timedelta(days=8)).isoformat(),
                "reason": "Leave",
            },
        ]
    ).execute()
    force_complaint = raise_complaint("Critical leak", "high")
    force_job = create_job(manager, force_complaint, 7)
    manager.rpc(
        "assign_work_order",
        {
            "p_work_order_id": force_job,
            "p_staff_assignment_id": worker_a_staff,
            "p_scheduled_start_at": None,
            "p_scheduled_end_at": None,
        },
    ).execute()
    worker_a.rpc(
        "decline_work_order_offer",
        {"p_work_order_id": force_job, "p_reason": "Unavailable"},
    ).execute()
    forced = (
        service.table("work_order_assignments")
        .select("status,is_forced")
        .eq("work_order_id", force_job)
        .eq("is_forced", True)
        .single()
        .execute()
        .data
    )
    assert forced == {"status": "accepted", "is_forced": True}
    with pytest.raises(APIError):
        worker_a.rpc(
            "decline_work_order_offer",
            {"p_work_order_id": force_job, "p_reason": "No"},
        ).execute()

    # Resident cancellation ownership and repool flag clearing still work.
    cancel_complaint = raise_complaint("Cancel me")
    cancel_job = create_job(supervisor, cancel_complaint, 9)
    supervisor.rpc(
        "assign_work_order",
        {
            "p_work_order_id": cancel_job,
            "p_staff_assignment_id": worker_a_staff,
            "p_scheduled_start_at": None,
            "p_scheduled_end_at": None,
        },
    ).execute()
    with pytest.raises(APIError):
        other_resident.rpc(
            "resident_cancel_work",
            {
                "p_complaint_id": cancel_complaint,
                "p_mode": "cancel",
                "p_reason": "Not mine",
            },
        ).execute()
    resident.rpc(
        "resident_cancel_work",
        {
            "p_complaint_id": cancel_complaint,
            "p_mode": "cancel",
            "p_reason": "No longer needed",
        },
    ).execute()
    assert _status(service, cancel_complaint) == "cancelled"

    pool_complaint = raise_complaint("Find someone else")
    pool_job = create_job(manager, pool_complaint, 10)
    manager.rpc(
        "assign_work_order",
        {
            "p_work_order_id": pool_job,
            "p_staff_assignment_id": worker_a_staff,
            "p_scheduled_start_at": None,
            "p_scheduled_end_at": None,
        },
    ).execute()
    resident.rpc(
        "resident_cancel_work",
        {
            "p_complaint_id": pool_complaint,
            "p_mode": "repool",
            "p_reason": "Try another",
        },
    ).execute()
    returned_to_pool = (
        service.table("complaints")
        .select("returned_to_pool_at")
        .eq("id", pool_complaint)
        .single()
        .execute()
        .data["returned_to_pool_at"]
    )
    assert returned_to_pool is not None
    create_job(manager, pool_complaint, 11)
    returned_to_pool = (
        service.table("complaints")
        .select("returned_to_pool_at")
        .eq("id", pool_complaint)
        .single()
        .execute()
        .data["returned_to_pool_at"]
    )
    assert returned_to_pool is None
    with pytest.raises(APIError):
        service.table("complaint_events").insert(
            {
                "complaint_id": pool_complaint,
                "event_type": "not-a-vocabulary-event",
            }
        ).execute()
