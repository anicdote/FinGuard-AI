"""
PHASE 11 — End-to-end integration test.

Exercises the REAL pipeline (actual trained XGBoost/IsolationForest models,
actual Adaptive Planner, actual 6 agents, actual CaseService) against an
in-memory Mongo, then drives the actual FastAPI route handlers for every
human-in-the-loop / false-positive / audit / analytics feature built in
Phases 7-10. Nothing here is mocked except the database.
"""
import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient
from bson import ObjectId

import app.db.session as session_mod
from app.core.security import get_current_user
import app.main as main_mod
from app.workers.background import analyze_pending_transactions
from app.db.repositories.transaction_repo import TransactionRepository
from app.db.repositories.case_repo import CaseRepository


async def main():
    mock_client = AsyncMongoMockClient()
    session_mod._db = mock_client["finguard_e2e"]
    db = session_mod._db
    results = {}

    # ── Seed users ─────────────────────────────────────────────────────────
    officer = {"_id": ObjectId(), "email": "o@finguard.ai", "name": "Officer One", "role": "officer",
               "hashed_password": "x", "is_active": True}
    manager = {"_id": ObjectId(), "email": "m@finguard.ai", "name": "Manager Meera", "role": "manager",
               "hashed_password": "x", "is_active": True}
    for u in (officer, manager):
        await db.users.insert_one(dict(u))
    officer["_id"] = str(officer["_id"])
    manager["_id"] = str(manager["_id"])

    # ── STEP 1: create a high-risk transaction directly via TransactionRepository
    #    (mirrors what POST /transactions/ does — analyzed stays False) ───────
    txn_repo = TransactionRepository(db)
    txn = await txn_repo.create({
        "account_id": "ACC-E2E-001",
        "accountName": "E2E Test Subject",
        "amount": 950000,             # near CTR threshold — triggers near_ctr feature
        "oldbalanceOrg": 950000,
        "newbalanceOrig": 0,          # balance drain
        "hour": 2,                    # night hour
        "location": "Dubai",          # high-risk location
        "channel": "Wire Transfer",
        "paySimType": "TRANSFER",
        "analyzed": False,
    })
    results["step1_transaction_created"] = {"analyzed": txn.get("analyzed")}

    # ── STEP 2: run one real background-worker cycle (Adaptive Planner + 6 agents) ──
    await analyze_pending_transactions()

    txn_after = await db.transactions.find_one({"_id": ObjectId(txn["_id"])})
    results["step2_transaction_after_pipeline"] = {
        "analyzed": txn_after.get("analyzed"),
        "fraud_probability": txn_after.get("fraud_probability"),
        "is_fraud": txn_after.get("is_fraud"),
    }

    case_repo = CaseRepository(db)
    cases = await case_repo.list_all(limit=10)
    results["step2_cases_created"] = len(cases)
    if not cases:
        print("FATAL: no case was created by the pipeline — aborting further steps.")
        import json
        print(json.dumps(results, indent=2, default=str))
        return

    case = cases[0]
    case_id = case["id"]
    results["step2_case_summary"] = {
        "risk_score": case.get("risk_score"),
        "priority": case.get("priority"),
        "recommendation_action": (case.get("recommendation") or {}).get("action"),
        "agent_log_entries": len(case.get("agent_log", [])),
        "has_shap": len(case.get("shap_values", [])) > 0,
    }

    # ── STEP 3: manager assigns the case to the officer ───────────────────────
    transport = ASGITransport(app=main_mod.app)

    async def as_user(user):
        main_mod.app.dependency_overrides[get_current_user] = lambda u=user: u

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await as_user(manager)
        r = await client.post(f"/api/v1/cases/{case_id}/assign", json={"officer_id": officer["_id"]})
        results["step3_assign"] = (r.status_code, r.json())

        # invalid officer id shouldn't 500 (Phase 8 ObjectId bug check)
        r = await client.post(f"/api/v1/cases/{case_id}/assign", json={"officer_id": "not-a-valid-object-id"})
        results["step3_assign_invalid_id_status"] = r.status_code  # must be 404, not 500

        # ── STEP 4: officer opens their assigned case ──────────────────────────
        await as_user(officer)
        r = await client.get(f"/api/v1/cases/{case_id}")
        results["step4_officer_opens_case"] = r.status_code

        # ── STEP 5: officer overrides the AI recommendation ─────────────────────
        r = await client.post(
            f"/api/v1/cases/{case_id}/review/override",
            json={"decision": "ESCALATE", "reason": "High-risk corridor confirmed via manual KYC check."},
        )
        results["step5_override"] = (r.status_code, r.json().get("human_review", {}).get("status"))

        # ── STEP 6: officer marks the case a false positive ─────────────────────
        r = await client.post(
            f"/api/v1/cases/{case_id}/false-positive",
            json={"reason": "Model false positive", "notes": "Confirmed legitimate NRI remittance."},
        )
        results["step6_false_positive"] = (r.status_code, r.json())

        # ── STEP 7: audit trail should now contain case_created, case_assigned,
        #    human_review_overridden, false_positive_recorded ─────────────────
        r = await client.get(f"/api/v1/cases/{case_id}/audit")
        audit_actions = [e["action"] for e in r.json()]
        results["step7_audit_trail"] = (r.status_code, audit_actions)

        # ── STEP 8: false-positive stats endpoint ───────────────────────────────
        r = await client.get("/api/v1/cases/false-positive-stats")
        results["step8_fp_stats"] = (r.status_code, r.json())

        # ── STEP 9: analytics dashboard must not crash (average_risk_score regression check) ──
        r = await client.get("/api/v1/analytics/dashboard")
        results["step9_dashboard_status"] = r.status_code
        results["step9_dashboard_avg_risk"] = r.json().get("averageRiskScore") if r.status_code == 200 else r.text

        # ── STEP 10: officer2 (unassigned) cannot see this case ────────────────
        officer2 = {"_id": str(ObjectId()), "email": "o2@finguard.ai", "name": "Officer Two", "role": "officer"}
        await as_user(officer2)
        r = await client.get(f"/api/v1/cases/{case_id}")
        results["step10_other_officer_blocked"] = r.status_code

    import json
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
