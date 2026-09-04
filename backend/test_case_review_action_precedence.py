"""Regression tests for canonical Agent 6 actions in human-review routes."""

import asyncio
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import app.db.session as session_mod
import app.main as main_mod
from app.api.routes.cases import _get_recommendation_action
from app.core.security import get_current_user


def test_recommendation_action_precedence_supports_legacy_and_agent6_fields():
    assert _get_recommendation_action({"action": "CLOSE"}) == "CLOSE"
    assert _get_recommendation_action({"action": "CLOSE", "decision": "ESCALATE"}) == "ESCALATE"
    assert _get_recommendation_action({"action": "CLOSE", "decision": "ESCALATE", "case_action": "BLOCK"}) == "BLOCK"


def test_review_routes_record_canonical_agent6_action_and_override_selection():
    asyncio.run(_exercise_review_routes())


async def _exercise_review_routes():
    mock_client = AsyncMongoMockClient()
    session_mod._db = mock_client["finguard_review_precedence_test"]
    db = session_mod._db
    fake_user = {"_id": "officer-1", "email": "officer@example.test", "name": "Officer", "role": "analyst"}
    main_mod.app.dependency_overrides[get_current_user] = lambda: fake_user

    def case_doc(recommendation):
        return {
            "id": str(uuid.uuid4()),
            "account_id": "ACC-TEST",
            "status": "new",
            "transaction_ids": [str(ObjectId())],
            "recommendation": recommendation,
            "str_filing_status": "not_filed",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    accept_case = case_doc({"action": "CLOSE", "decision": "ESCALATE", "case_action": "BLOCK"})
    override_case = case_doc({"action": "CLOSE", "decision": "ESCALATE"})
    evidence_case = case_doc({"action": "CLOSE", "decision": "ESCALATE", "case_action": "BLOCK"})
    await db.cases.insert_many([accept_case, override_case, evidence_case])
    await db.transactions.insert_one({"_id": ObjectId(evidence_case["transaction_ids"][0]), "analyzed": True})

    try:
        async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
            accept = await client.post(f"/api/v1/cases/{accept_case['id']}/review/accept")
            assert accept.status_code == 200
            assert accept.json()["human_review"]["previous_recommendation"] == "BLOCK"
            assert accept.json()["human_review"]["final_decision"] == "BLOCK"

            override = await client.post(
                f"/api/v1/cases/{override_case['id']}/review/override",
                json={"decision": "MONITOR", "reason": "Customer documentation supports monitoring."},
            )
            assert override.status_code == 200
            assert override.json()["human_review"]["previous_recommendation"] == "ESCALATE"
            assert override.json()["human_review"]["final_decision"] == "MONITOR"

            evidence = await client.post(
                f"/api/v1/cases/{evidence_case['id']}/review/more-evidence",
                json={"request": "Obtain counterparty statements."},
            )
            assert evidence.status_code == 200
            assert evidence.json()["human_review"]["previous_recommendation"] == "BLOCK"

        saved = await db.cases.find_one({"id": accept_case["id"]})
        assert saved["human_review"]["previous_recommendation"] == "BLOCK"
        assert saved["str_filing_status"] == "not_filed"
        evidence_audit = await db.audit_logs.find_one({"case_id": evidence_case["id"], "action": "more_evidence_requested"})
        assert evidence_audit["metadata"]["previous_recommendation"] == "BLOCK"
    finally:
        main_mod.app.dependency_overrides.pop(get_current_user, None)
