"""Real local-Supabase service-professional flow using authenticated user JWTs."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from supabase import Client, create_client

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_INTEGRATION") != "1",
    reason="requires the local Supabase stack",
)


def _signed_in_user(
    service: Client, url: str, anon_key: str, label: str
) -> tuple[Client, str]:
    suffix = uuid4().hex
    email = f"{label}-{suffix}@example.test"
    password = f"HomeBandhu-{suffix}-Password!"
    created = service.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    user_id = str(created.user.id)
    service.table("profiles").insert(
        {"id": user_id, "full_name": label.title(), "display_email": email}
    ).execute()
    client = create_client(url, anon_key)
    client.auth.sign_in_with_password({"email": email, "password": password})
    return client, user_id


def _register_provider(
    client: Client,
    *,
    skill_id: str,
    latitude: float,
    longitude: float,
    radius_km: int = 15,
    name: str = "Ravi Kumar",
) -> str:
    return str(
        client.rpc(
            "register_service_provider",
            {
                "p_display_name": name,
                "p_headline": "Licensed professional",
                "p_phone_e164": "+919876543210",
                "p_latitude": latitude,
                "p_longitude": longitude,
                "p_service_radius_km": radius_km,
                "p_skill_ids": [skill_id],
            },
        )
        .execute()
        .data
    )


def test_service_professional_flow_with_real_user_jwts() -> None:
    url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    service = create_client(url, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    provider, provider_profile = _signed_in_user(service, url, anon_key, "provider")
    manager, manager_profile = _signed_in_user(service, url, anon_key, "manager")
    admin, admin_profile = _signed_in_user(service, url, anon_key, "admin")

    skill_id = (
        service.table("skills")
        .select("id")
        .eq("name", "Plumbing")
        .single()
        .execute()
        .data["id"]
    )
    registered = _register_provider(
        provider,
        skill_id=skill_id,
        latitude=22.572645,
        longitude=88.363892,
    )
    assert registered

    with pytest.raises(APIError):
        provider.rpc(
            "register_service_provider",
            {
                "p_display_name": "Must Roll Back",
                "p_headline": None,
                "p_phone_e164": None,
                "p_latitude": 22.572645,
                "p_longitude": 88.363892,
                "p_service_radius_km": 15,
                "p_skill_ids": [str(uuid4())],
            },
        ).execute()
    saved = (
        service.table("service_providers")
        .select("display_name")
        .eq("id", registered)
        .single()
        .execute()
        .data
    )
    assert saved["display_name"] == "Ravi Kumar"

    community_id = str(uuid4())
    far_community_id = str(uuid4())
    service.table("communities").insert(
        [
            {
                "id": community_id,
                "name": "Near Community",
                "community_type": "apartment",
                "address_line1": "1 Test Road",
                "city": "Kolkata",
                "state": "West Bengal",
                "postal_code": "700001",
                "latitude": 22.572645,
                "longitude": 88.363892,
            },
            {
                "id": far_community_id,
                "name": "Far Community",
                "community_type": "apartment",
                "address_line1": "2 Test Road",
                "city": "Distant",
                "state": "West Bengal",
                "postal_code": "700002",
                "latitude": 24.0,
                "longitude": 88.363892,
            },
        ]
    ).execute()
    department_id = str(uuid4())
    far_department_id = str(uuid4())
    service.table("departments").insert(
        [
            {
                "id": department_id,
                "community_id": community_id,
                "name": "Maintenance",
                "kind": "service",
            },
            {
                "id": far_department_id,
                "community_id": far_community_id,
                "name": "Maintenance",
                "kind": "service",
            },
        ]
    ).execute()
    categories = (
        service.table("complaint_categories")
        .insert(
            [
                {
                    "community_id": community_id,
                    "name": "Plumbing",
                    "skill_id": skill_id,
                },
                {
                    "community_id": far_community_id,
                    "name": "Plumbing",
                    "skill_id": skill_id,
                },
            ]
        )
        .execute()
        .data
    )
    service.table("department_categories").insert(
        [
            {"department_id": department_id, "category_id": categories[0]["id"]},
            {"department_id": far_department_id, "category_id": categories[1]["id"]},
        ]
    ).execute()

    found = (
        provider.rpc(
            "search_serviceable_communities",
            {"p_query": None, "p_limit": 100, "p_offset": 0},
        )
        .execute()
        .data
    )
    assert [row["id"] for row in found] == [community_id]

    admin_membership = (
        service.table("community_memberships")
        .insert(
            {
                "community_id": community_id,
                "profile_id": admin_profile,
                "role": "admin",
                "status": "active",
            }
        )
        .execute()
        .data[0]["id"]
    )
    assert (
        admin.rpc("can_hire_for_department", {"p_department_id": department_id})
        .execute()
        .data
        is True
    )

    fallback_application = (
        provider.rpc(
            "apply_to_department",
            {"p_department_id": department_id, "p_message": "Fallback check"},
        )
        .execute()
        .data
    )
    fallback_notices = (
        service.table("notifications")
        .select("recipient_membership_id")
        .eq("kind", "service_application_received")
        .execute()
        .data
    )
    assert {row["recipient_membership_id"] for row in fallback_notices} == {
        admin_membership
    }
    provider.rpc(
        "decide_service_application",
        {
            "p_application_id": fallback_application,
            "p_decision": "withdrawn",
            "p_rank": None,
            "p_job_title": None,
            "p_shift": None,
            "p_note": None,
        },
    ).execute()
    service.table("notifications").delete().eq(
        "kind", "service_application_received"
    ).execute()

    manager_membership = (
        service.table("community_memberships")
        .insert(
            {
                "community_id": community_id,
                "profile_id": manager_profile,
                "department_id": department_id,
                "role": "manager",
                "status": "active",
            }
        )
        .execute()
        .data[0]["id"]
    )
    assert (
        manager.rpc("can_hire_for_department", {"p_department_id": department_id})
        .execute()
        .data
        is True
    )
    assert (
        admin.rpc("can_hire_for_department", {"p_department_id": department_id})
        .execute()
        .data
        is False
    )

    supervisor, supervisor_profile = _signed_in_user(
        service, url, anon_key, "supervisor"
    )
    supervisor_membership = (
        service.table("community_memberships")
        .insert(
            {
                "community_id": community_id,
                "profile_id": supervisor_profile,
                "department_id": department_id,
                "role": "worker",
                "status": "active",
            }
        )
        .execute()
        .data[0]["id"]
    )
    service.table("staff_assignments").insert(
        {
            "community_id": community_id,
            "department_id": department_id,
            "membership_id": supervisor_membership,
            "display_name": "Supervisor",
            "rank": "supervisor",
            "status": "active",
            "employment_type": "staff",
        }
    ).execute()
    assert (
        supervisor.rpc(
            "can_hire_for_department", {"p_department_id": department_id}
        )
        .execute()
        .data
        is False
    )

    unrelated_manager, unrelated_profile = _signed_in_user(
        service, url, anon_key, "unrelated-manager"
    )
    service.table("community_memberships").insert(
        {
            "community_id": far_community_id,
            "profile_id": unrelated_profile,
            "department_id": far_department_id,
            "role": "manager",
            "status": "active",
        }
    ).execute()
    assert (
        unrelated_manager.rpc(
            "can_hire_for_department", {"p_department_id": department_id}
        )
        .execute()
        .data
        is False
    )
    with pytest.raises(APIError):
        unrelated_manager.rpc(
            "search_hireable_service_providers",
            {
                "p_department_id": department_id,
                "p_query": None,
                "p_limit": 20,
                "p_offset": 0,
            },
        ).execute()

    invitee, _ = _signed_in_user(service, url, anon_key, "invitee")
    invitee_provider = _register_provider(
        invitee,
        skill_id=skill_id,
        latitude=22.572645,
        longitude=88.363892,
        name="Invited Plumber",
    )
    invitation_id = (
        manager.rpc(
            "invite_service_provider",
            {
                "p_department_id": department_id,
                "p_service_provider_id": invitee_provider,
                "p_message": "Join us",
                "p_rank": "member",
                "p_job_title": "Offered Plumber",
                "p_shift": "Day",
            },
        )
        .execute()
        .data
    )
    invitation_staff = (
        invitee.rpc(
            "decide_service_application",
            {
                "p_application_id": invitation_id,
                "p_decision": "accepted",
                "p_rank": "manager",
                "p_job_title": "Changed by invitee",
                "p_shift": "Night",
                "p_note": None,
            },
        )
        .execute()
        .data
    )
    immutable_terms = (
        service.table("staff_assignments")
        .select("rank,job_title,shift")
        .eq("id", invitation_staff)
        .single()
        .execute()
        .data
    )
    assert immutable_terms == {
        "rank": "member",
        "job_title": "Offered Plumber",
        "shift": "Day",
    }

    candidates = (
        manager.rpc(
            "search_hireable_service_providers",
            {
                "p_department_id": department_id,
                "p_query": None,
                "p_limit": 100,
                "p_offset": 0,
            },
        )
        .execute()
        .data
    )
    assert [row["id"] for row in candidates] == [registered]

    application_id = (
        provider.rpc(
            "apply_to_department",
            {"p_department_id": department_id, "p_message": "Available weekdays."},
        )
        .execute()
        .data
    )
    notices = (
        service.table("notifications")
        .select("recipient_membership_id")
        .eq("kind", "service_application_received")
        .execute()
        .data
    )
    assert {row["recipient_membership_id"] for row in notices} == {manager_membership}
    assert admin_membership not in {row["recipient_membership_id"] for row in notices}

    with pytest.raises(APIError):
        manager.rpc(
            "decide_service_application",
            {
                "p_application_id": application_id,
                "p_decision": "accepted",
                "p_rank": "not-a-real-rank",
                "p_job_title": "Plumber",
                "p_shift": "Day",
                "p_note": None,
            },
        ).execute()
    assert (
        service.table("service_applications")
        .select("status")
        .eq("id", application_id)
        .single()
        .execute()
        .data["status"]
        == "pending"
    )

    session = manager.auth.get_session()

    def decide_once() -> tuple[str, str]:
        concurrent_manager = create_client(url, anon_key)
        concurrent_manager.auth.set_session(
            session.access_token, session.refresh_token
        )
        try:
            result = concurrent_manager.rpc(
                "decide_service_application",
                {
                    "p_application_id": application_id,
                    "p_decision": "accepted",
                    "p_rank": "member",
                    "p_job_title": "Plumber",
                    "p_shift": "Day",
                    "p_note": None,
                },
            ).execute()
            return "accepted", str(result.data)
        except APIError as exc:
            return "conflict", exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: decide_once(), range(2)))
    assert sorted(outcome[0] for outcome in outcomes) == ["accepted", "conflict"]
    staff_id = next(value for status, value in outcomes if status == "accepted")
    assert staff_id
    membership = (
        service.table("community_memberships")
        .select("role,department_id")
        .eq("profile_id", provider_profile)
        .eq("community_id", community_id)
        .single()
        .execute()
        .data
    )
    assert membership == {"role": "worker", "department_id": department_id}
    staff = (
        service.table("staff_assignments")
        .select("service_provider_id,status")
        .eq("id", staff_id)
        .single()
        .execute()
        .data
    )
    assert staff == {"service_provider_id": registered, "status": "active"}
    assert (
        service.table("staff_assignments")
        .select("id", count="exact", head=True)
        .eq("service_provider_id", registered)
        .execute()
        .count
        == 1
    )

    security_community = str(uuid4())
    security_department = str(uuid4())
    service.table("communities").insert(
        {
            "id": security_community,
            "name": "Nearby Security Community",
            "community_type": "apartment",
            "address_line1": "3 Test Road",
            "city": "Kolkata",
            "state": "West Bengal",
            "postal_code": "700003",
            "latitude": 22.572645,
            "longitude": 88.363892,
        }
    ).execute()
    service.table("departments").insert(
        {
            "id": security_department,
            "community_id": security_community,
            "name": "Security",
            "kind": "security",
        }
    ).execute()
    category = (
        service.table("complaint_categories")
        .insert(
            {
                "community_id": security_community,
                "name": "Security plumbing fixture",
                "skill_id": skill_id,
            }
        )
        .execute()
        .data[0]
    )
    service.table("department_categories").insert(
        {"department_id": security_department, "category_id": category["id"]}
    ).execute()
    service.table("community_memberships").insert(
        {
            "community_id": security_community,
            "profile_id": admin_profile,
            "role": "admin",
            "status": "active",
        }
    ).execute()

    after_hire = (
        provider.rpc(
            "search_serviceable_communities",
            {"p_query": "Nearby Security", "p_limit": 20, "p_offset": 0},
        )
        .execute()
        .data
    )
    assert after_hire == []
    with pytest.raises(APIError):
        admin.rpc(
            "invite_service_provider",
            {
                "p_department_id": security_department,
                "p_service_provider_id": registered,
                "p_message": None,
                "p_rank": "member",
                "p_job_title": "Guard",
                "p_shift": "Day",
            },
        ).execute()


def test_radius_boundary_stable_top_twenty_and_name_filter() -> None:
    url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    service = create_client(url, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    provider, _ = _signed_in_user(service, url, anon_key, "radius-provider")
    skill_id = (
        service.table("skills")
        .select("id")
        .eq("name", "Electrical")
        .single()
        .execute()
        .data["id"]
    )
    _register_provider(
        provider, skill_id=skill_id, latitude=0, longitude=0, name="Radius Tester"
    )

    communities = []
    for index in range(21):
        communities.append(
            {
                "id": str(uuid4()),
                "name": f"Boundary Community {index:02d}",
                "community_type": "apartment",
                "address_line1": f"{index} Boundary Road",
                "city": "Test City",
                "state": "Test State",
                "postal_code": f"8{index:05d}",
                "latitude": 0,
                "longitude": 0,
            }
        )
    communities.extend(
        [
            {
                "id": str(uuid4()),
                "name": "Exact Radius Community",
                "community_type": "apartment",
                "address_line1": "Exact Road",
                "city": "Test City",
                "state": "Test State",
                "postal_code": "899991",
                "latitude": 0,
                "longitude": 0.1347472926179282,
            },
            {
                "id": str(uuid4()),
                "name": "Beyond Radius Community",
                "community_type": "apartment",
                "address_line1": "Beyond Road",
                "city": "Test City",
                "state": "Test State",
                "postal_code": "899992",
                "latitude": 0,
                "longitude": 0.13476,
            },
            {
                "id": str(uuid4()),
                "name": "Missing Coordinates Community",
                "community_type": "apartment",
                "address_line1": "Missing Road",
                "city": "Test City",
                "state": "Test State",
                "postal_code": "899993",
            },
        ]
    )
    service.table("communities").insert(communities).execute()
    departments = [
        {
            "id": str(uuid4()),
            "community_id": community["id"],
            "name": "Electrical",
            "kind": "service",
        }
        for community in communities
    ]
    service.table("departments").insert(departments).execute()
    categories = (
        service.table("complaint_categories")
        .insert(
            [
                {
                    "community_id": community["id"],
                    "name": "Electrical",
                    "skill_id": skill_id,
                }
                for community in communities
            ]
        )
        .execute()
        .data
    )
    service.table("department_categories").insert(
        [
            {"department_id": department["id"], "category_id": category["id"]}
            for department, category in zip(departments, categories, strict=True)
        ]
    ).execute()

    page = (
        provider.rpc(
            "search_serviceable_communities",
            {"p_query": None, "p_limit": 100, "p_offset": 0},
        )
        .execute()
        .data
    )
    assert len(page) == 20
    assert [row["name"] for row in page] == [
        f"Boundary Community {index:02d}" for index in range(20)
    ]
    second_page = (
        provider.rpc(
            "search_serviceable_communities",
            {"p_query": None, "p_limit": 20, "p_offset": 20},
        )
        .execute()
        .data
    )
    assert [row["name"] for row in second_page] == [
        "Boundary Community 20",
        "Exact Radius Community",
    ]
    assert second_page[1]["distance_km"] == 15

    filtered = (
        provider.rpc(
            "search_serviceable_communities",
            {"p_query": "Community 20", "p_limit": 1, "p_offset": 0},
        )
        .execute()
        .data
    )
    assert [row["name"] for row in filtered] == ["Boundary Community 20"]
    for excluded_name in ("Beyond Radius", "Missing Coordinates"):
        assert (
            provider.rpc(
                "search_serviceable_communities",
                {"p_query": excluded_name, "p_limit": 20, "p_offset": 0},
            )
            .execute()
            .data
            == []
        )


def test_concurrent_registration_creates_one_complete_provider() -> None:
    url = os.environ["SUPABASE_URL"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    service = create_client(url, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    provider, profile_id = _signed_in_user(
        service, url, anon_key, "concurrent-provider"
    )
    skill_id = (
        service.table("skills")
        .select("id")
        .eq("name", "Carpentry")
        .single()
        .execute()
        .data["id"]
    )
    session = provider.auth.get_session()

    def register_once() -> str:
        concurrent_client = create_client(url, anon_key)
        concurrent_client.auth.set_session(
            session.access_token, session.refresh_token
        )
        return _register_provider(
            concurrent_client,
            skill_id=skill_id,
            latitude=12.9716,
            longitude=77.5946,
            name="Concurrent Carpenter",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        provider_ids = list(executor.map(lambda _: register_once(), range(2)))
    assert provider_ids[0] == provider_ids[1]
    assert (
        service.table("service_providers")
        .select("id", count="exact", head=True)
        .eq("profile_id", profile_id)
        .execute()
        .count
        == 1
    )
    skills = (
        service.table("service_provider_skills")
        .select("skill_id")
        .eq("service_provider_id", provider_ids[0])
        .execute()
        .data
    )
    assert skills == [{"skill_id": skill_id}]


def test_funnel_retention_removes_only_expired_events() -> None:
    service = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )
    expired = str(uuid4())
    current = str(uuid4())
    service.table("service_signup_funnel_events").insert(
        [
            {
                "visitor_id": expired,
                "event_name": "cta_impression",
                "occurred_at": "2020-01-01T00:00:00Z",
            },
            {"visitor_id": current, "event_name": "cta_impression"},
        ]
    ).execute()

    assert service.rpc("prune_service_signup_funnel_events").execute().data >= 1
    remaining = (
        service.table("service_signup_funnel_events")
        .select("*")
        .in_("visitor_id", [expired, current])
        .execute()
        .data
    )
    assert [row["visitor_id"] for row in remaining] == [current]
    assert set(remaining[0]) == {"visitor_id", "event_name", "occurred_at"}
