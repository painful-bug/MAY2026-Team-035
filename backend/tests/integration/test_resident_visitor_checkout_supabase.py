"""Real JWT ownership, state transitions, and concurrent visitor checkout."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Barrier
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from supabase import create_client

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_INTEGRATION") != "1",
    reason="requires the local Supabase stack",
)


def test_resident_checkout_real_jwt_and_gate_race():
    url = os.environ["SUPABASE_URL"]
    assert urlparse(url).hostname in {"localhost", "127.0.0.1"}
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    service = create_client(url, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    communities = [str(uuid4()), str(uuid4())]
    profiles = []
    clients = []
    members = []
    try:
        for community in communities:
            service.table("communities").insert(
                {
                    "id": community,
                    "name": f"Checkout {community}",
                    "community_type": "apartment",
                    "address_line1": "1 Test Road",
                    "city": "Kolkata",
                    "state": "West Bengal",
                    "postal_code": "700001",
                }
            ).execute()
        for index, role in enumerate(["resident", "resident", "security", "resident"]):
            suffix = uuid4().hex
            credentials = {
                "email": f"checkout-{suffix}@example.test",
                "password": f"Checkout-{suffix}!",
            }
            profile = str(
                service.auth.admin.create_user(
                    {**credentials, "email_confirm": True}
                ).user.id
            )
            profiles.append(profile)
            service.table("profiles").upsert(
                {
                    "id": profile,
                    "full_name": "Checkout Test",
                    "display_email": credentials["email"],
                }
            ).execute()
            client = create_client(url, anon_key)
            client.auth.sign_in_with_password(credentials)
            clients.append(client)
            member = (
                service.table("community_memberships")
                .insert(
                    {
                        "community_id": communities[int(index == 3)],
                        "profile_id": profile,
                        "role": role,
                        "status": "active",
                    }
                )
                .execute()
                .data[0]["id"]
            )
            members.append(member)

        def seed(status="checked_in", *, expired=False, count=1, outside=False):
            now = datetime.now(timezone.utc)
            pass_id = str(uuid4())
            pass_hash = sha256(pass_id.encode()).hexdigest()
            service.table("visitor_requests").insert(
                {
                    "id": pass_id,
                    "community_id": communities[int(outside)],
                    "requested_by_membership_id": members[3 if outside else 0],
                    "visitor_name": "Checkout Guest",
                    "purpose": "Guest",
                    "guest_count": count,
                    "status": status,
                    "pass_hash": pass_hash,
                    "valid_from": (now - timedelta(hours=2)).isoformat(),
                    "valid_until": (
                        now + timedelta(hours=-1 if expired else 1)
                    ).isoformat(),
                    "checked_in_at": (now - timedelta(hours=2)).isoformat()
                    if status == "checked_in"
                    else None,
                }
            ).execute()
            if status == "checked_in":
                service.table("visitor_events").insert(
                    {
                        "visitor_request_id": pass_id,
                        "actor_membership_id": members[3 if outside else 2],
                        "event_type": "checked_in",
                    }
                ).execute()
            return pass_id, pass_hash

        def checkout(pass_id, *, caller=0, member=None):
            return (
                clients[caller]
                .rpc(
                    "checkout_visitor_pass",
                    {
                        "p_membership_id": member or members[caller],
                        "p_pass_id": pass_id,
                    },
                )
                .execute()
            )

        def record(pass_id):
            return (
                service.table("visitor_requests")
                .select("*")
                .eq("id", pass_id)
                .single()
                .execute()
                .data
            )

        def departures(pass_id):
            return (
                service.table("visitor_events")
                .select("*")
                .eq("visitor_request_id", pass_id)
                .eq("event_type", "checked_out")
                .execute()
                .data
            )

        def refuses(code, action):
            with pytest.raises(APIError) as error:
                action()
            assert error.value.code == code

        pass_id, _ = seed(expired=True, count=3)
        refuses("HB403", lambda: checkout(pass_id, caller=1, member=members[0]))
        refuses("HB404", lambda: checkout(pass_id, caller=1))
        refuses("HB404", lambda: checkout(str(uuid4())))
        outside_id, _ = seed(outside=True)
        refuses("HB404", lambda: checkout(outside_id))
        service.table("community_memberships").update({"status": "suspended"}).eq(
            "id", members[0]
        ).execute()
        refuses("HB403", lambda: checkout(pass_id))
        service.table("community_memberships").update({"status": "active"}).eq(
            "id", members[0]
        ).execute()
        for status in [
            "expected",
            "pending_approval",
            "approved",
            "denied",
            "cancelled",
        ]:
            invalid_id, _ = seed(status)
            refuses("HB409", lambda invalid_id=invalid_id: checkout(invalid_id))
            assert record(invalid_id)["status"] == status
            assert departures(invalid_id) == []

        checkout(pass_id)
        closed = record(pass_id)
        assert closed["status"] == "checked_out"
        assert closed["checked_out_at"] > closed["checked_in_at"]
        assert len(departures(pass_id)) == 1
        assert departures(pass_id)[0]["actor_membership_id"] == members[0]
        overview = (
            clients[0]
            .table("visitor_pass_overview")
            .select("*")
            .eq("id", pass_id)
            .single()
            .execute()
            .data
        )
        assert overview["is_current"] is False
        checkout(pass_id)
        assert record(pass_id)["checked_out_at"] == closed["checked_out_at"]
        assert len(departures(pass_id)) == 1
        notifications = (
            service.table("notifications")
            .select("payload")
            .eq("recipient_membership_id", members[2])
            .eq("kind", "visitor.checked_out")
            .execute()
            .data
        )
        assert any(row["payload"]["pass_id"] == pass_id for row in notifications)

        # Independent HTTP clients use the same owner's JWT for simultaneous retries.
        second_owner = create_client(url, anon_key)
        second_owner.postgrest.auth(clients[0].auth.get_session().access_token)
        for race_with_gate in [False, True]:
            race_id, race_hash = seed()
            barrier = Barrier(2)

            def resident_call(barrier=barrier, race_id=race_id):
                barrier.wait(timeout=10)
                checkout(race_id)

            def competing_call(
                barrier=barrier,
                race_with_gate=race_with_gate,
                race_hash=race_hash,
                race_id=race_id,
            ):
                barrier.wait(timeout=10)
                if race_with_gate:
                    return (
                        clients[2]
                        .rpc(
                            "verify_gate_credential",
                            {
                                "p_membership_id": members[2],
                                "p_hash": race_hash,
                            },
                        )
                        .execute()
                        .data[0]["verdict"]
                    )
                second_owner.rpc(
                    "checkout_visitor_pass",
                    {
                        "p_membership_id": members[0],
                        "p_pass_id": race_id,
                    },
                ).execute()

            with ThreadPoolExecutor(max_workers=2) as executor:
                resident_future = executor.submit(resident_call)
                competing_future = executor.submit(competing_call)
                resident_future.result(timeout=30)
                verdict = competing_future.result(timeout=30)
            if race_with_gate:
                assert verdict in {"departed", "refused"}
            assert record(race_id)["status"] == "checked_out"
            assert len(departures(race_id)) == 1
            assert departures(race_id)[0]["actor_membership_id"] in {
                members[0],
                members[2],
            }
    finally:
        # Only delete the uniquely generated fixtures in this local test.
        for community in communities:
            service.table("visitor_requests").delete().eq(
                "community_id", community
            ).execute()
            # Membership deletion emits a community-scoped refresh event. Keep
            # the parent alive until those triggers have finished.
            service.table("community_memberships").delete().eq(
                "community_id", community
            ).execute()
            service.table("communities").delete().eq("id", community).execute()
        for profile in profiles:
            service.auth.admin.delete_user(profile)
