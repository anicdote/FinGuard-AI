"""
Standalone functional test for the Phase 7 human-in-the-loop review endpoints.
Runs against an in-memory Mongo (mongomock_motor) — no real database needed.
Not part of the app's permanent test suite; just used to verify the three
review flows (accept / override / request-more-evidence) actually work.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, ".")

from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

import app.db.session as session_mod
from app.core.security import get_current_user
import app.main as main_mod


async def main():
    # ── Wire an in-memory Mongo in place of the real connection ──────────
    mock_client = AsyncMongoMockClient()
    session_mod._db = mock_client["finguard_test"]
    db = session_mod._db

    # ── Seed a fake investigated case, as CaseService would produce ──────
    case_id = str(uuid.uuid4())
    txn_id_1 = str(__import__("bson").ObjectId())
    case_doc = {
        "id": case_id,
        "account_id": "ACC-TEST-001",
        "account_name": "Test Account",
        "status": "new",
        "priority": "critical",
        "risk_score": 91,
        "anomaly_score": 0.91,
        "transaction_ids": [txn_id_1],
        "suspicious_transactions": [],
        "recommendation": {
            "action": "BLOCK",
            "confidence": 0.89,
            "confidence_pct": 89,
            "reasoning": "High anomaly probability with confirmed watchlist hit.",
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.cases.insert_one(dict(case_doc))
    await db.transactions.insert_one({
        "_id": __import__("bson").ObjectId(txn_id_1),
        "account_id": "ACC-TEST-001",
        "amount": 500000,
        "analyzed": True,
    })

    # ── Fake authenticated user (bypass real JWT/DB lookup) ──────────────
    fake_user = {"_id": "user-1", "email": "officer@finguard.ai", "name": "Officer Rao", "role": "analyst"}
    main_mod.app.dependency_overrides[get_current_user] = lambda: fake_user

    transport = ASGITransport(app=main_mod.app)
    results = {}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ── 1. ACCEPT ─────────────────────────────────────────────────────
        r = await client.post(f"/api/v1/cases/{case_id}/review/accept")
        results["accept"] = (r.status_code, r.json())

        # ── 2. OVERRIDE (on a second fresh case, since a case's review can
        #      legitimately be re-decided, but we want a clean before/after) ──
        case_id_2 = str(uuid.uuid4())
        case_doc_2 = dict(case_doc)
        case_doc_2["id"] = case_id_2
        case_doc_2["account_id"] = "ACC-TEST-002"
        await db.cases.insert_one(case_doc_2)

        r = await client.post(
            f"/api/v1/cases/{case_id_2}/review/override",
            json={"decision": "MONITOR", "reason": "Customer provided satisfactory KYC documentation."},
        )
        results["override"] = (r.status_code, r.json())

        # Override with empty reason should be rejected
        r = await client.post(
            f"/api/v1/cases/{case_id_2}/review/override",
            json={"decision": "MONITOR", "reason": "   "},
        )
        results["override_no_reason"] = (r.status_code, r.json())

        # Override with an invalid decision should be rejected
        r = await client.post(
            f"/api/v1/cases/{case_id_2}/review/override",
            json={"decision": "DELETE_CASE", "reason": "test"},
        )
        results["override_bad_decision"] = (r.status_code, r.json())

        # ── 3. REQUEST MORE EVIDENCE (third case) ─────────────────────────
        case_id_3 = str(uuid.uuid4())
        txn_id_3 = str(__import__("bson").ObjectId())
        case_doc_3 = dict(case_doc)
        case_doc_3["id"] = case_id_3
        case_doc_3["account_id"] = "ACC-TEST-003"
        case_doc_3["transaction_ids"] = [txn_id_3]
        await db.cases.insert_one(case_doc_3)
        await db.transactions.insert_one({
            "_id": __import__("bson").ObjectId(txn_id_3),
            "account_id": "ACC-TEST-003",
            "amount": 250000,
            "analyzed": True,   # should flip to False if reopening is wired
        })

        r = await client.post(
            f"/api/v1/cases/{case_id_3}/review/more-evidence",
            json={"request": "Please pull 90-day statement for the counterparty account."},
        )
        results["more_evidence"] = (r.status_code, r.json())

        # Check whether the underlying transaction was actually reopened
        txn_after = await db.transactions.find_one({"_id": __import__("bson").ObjectId(txn_id_3)})
        results["txn_reopened"] = txn_after.get("analyzed")

        case_after = await db.cases.find_one({"id": case_id_3})
        results["case_status_after_more_evidence"] = case_after.get("status")

        # ── 4. Unauthenticated request should be rejected ─────────────────
        del main_mod.app.dependency_overrides[get_current_user]
        r = await client.post(f"/api/v1/cases/{case_id}/review/accept")
        results["unauthenticated"] = (r.status_code,)

    import json
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
