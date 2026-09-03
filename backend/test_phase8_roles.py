"""
Standalone functional test for Phase 8 — role-based case visibility & assignment.
Runs against an in-memory Mongo (mongomock_motor) — no real database needed.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, ".")

from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient
from bson import ObjectId

import app.db.session as session_mod
from app.core.security import get_current_user
import app.main as main_mod


async def main():
    mock_client = AsyncMongoMockClient()
    session_mod._db = mock_client["finguard_test8"]
    db = session_mod._db

    officer = {"_id": str(ObjectId()), "email": "officer1@finguard.ai", "name": "Officer One", "role": "officer"}
    officer2 = {"_id": str(ObjectId()), "email": "officer2@finguard.ai", "name": "Officer Two", "role": "officer"}
    manager = {"_id": str(ObjectId()), "email": "manager@finguard.ai", "name": "Manager Meera", "role": "manager"}
    admin   = {"_id": str(ObjectId()), "email": "admin@finguard.ai",   "name": "Admin Ada",     "role": "admin"}

    for u in (officer, officer2, manager, admin):
        doc = dict(u)
        doc["_id"] = ObjectId(doc["_id"])
        doc["hashed_password"] = "x"
        doc["is_active"] = True
        await db.users.insert_one(doc)

    # Two cases: one will be assigned to officer1, one left unassigned
    case_a = str(uuid.uuid4())
    case_b = str(uuid.uuid4())
    for cid in (case_a, case_b):
        await db.cases.insert_one({
            "id": cid, "account_id": f"ACC-{cid[:6]}", "status": "new", "priority": "high",
            "risk_score": 80, "recommendation": {"action": "MONITOR"},
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        })

    transport = ASGITransport(app=main_mod.app)
    results = {}

    async def as_user(user):
        main_mod.app.dependency_overrides[get_current_user] = lambda u=user: u

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ── Officer with no assigned cases sees nothing ──────────────────
        await as_user(officer)
        r = await client.get("/api/v1/cases/")
        results["officer_before_assignment_count"] = len(r.json())

        # ── Officer cannot list other users (not manager/admin) ──────────
        r = await client.get("/api/v1/users/officers")
        results["officer_list_officers_status"] = r.status_code

        # ── Officer cannot assign cases ───────────────────────────────────
        r = await client.post(f"/api/v1/cases/{case_a}/assign", json={"officer_id": officer["_id"]})
        results["officer_assign_status"] = r.status_code

        # ── Manager lists officers ────────────────────────────────────────
        await as_user(manager)
        r = await client.get("/api/v1/users/officers")
        results["manager_list_officers"] = (r.status_code, [o["email"] for o in r.json()])

        # ── Manager assigns case_a to officer1 ────────────────────────────
        r = await client.post(f"/api/v1/cases/{case_a}/assign", json={"officer_id": officer["_id"]})
        results["manager_assign"] = (r.status_code, r.json())

        # ── Manager sees ALL cases regardless of assignment ───────────────
        r = await client.get("/api/v1/cases/")
        results["manager_sees_all_count"] = len(r.json())

        # ── Officer1 now sees exactly their 1 assigned case ───────────────
        await as_user(officer)
        r = await client.get("/api/v1/cases/")
        results["officer_after_assignment_count"] = len(r.json())
        r = await client.get(f"/api/v1/cases/{case_a}")
        results["officer_can_open_assigned_case"] = r.status_code

        # ── Officer1 CANNOT open the still-unassigned case_b ──────────────
        r = await client.get(f"/api/v1/cases/{case_b}")
        results["officer_cannot_open_unassigned_case"] = r.status_code

        # ── Officer2 (not assigned) cannot open officer1's case ───────────
        await as_user(officer2)
        r = await client.get(f"/api/v1/cases/{case_a}")
        results["officer2_cannot_open_officer1_case"] = r.status_code

        # ── Admin sees everything too ──────────────────────────────────────
        await as_user(admin)
        r = await client.get("/api/v1/cases/")
        results["admin_sees_all_count"] = len(r.json())
        r = await client.get(f"/api/v1/cases/{case_b}")
        results["admin_can_open_any_case"] = r.status_code

        # ── Assigning to a non-officer role should fail ────────────────────
        r = await client.post(f"/api/v1/cases/{case_b}/assign", json={"officer_id": manager["_id"]})
        results["cannot_assign_to_manager"] = r.status_code

    import json
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
