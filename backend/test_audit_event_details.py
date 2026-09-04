"""Regression coverage for persisted audit details consumed by the UI."""

import asyncio

from app.db.repositories.audit_repo import AuditRepository


class _InsertResult:
    inserted_id = "audit-id"


class _Collection:
    def __init__(self):
        self.document = None

    async def insert_one(self, document):
        self.document = document
        return _InsertResult()


class _Database:
    def __init__(self):
        self.audit_logs = _Collection()


def record(action, metadata):
    db = _Database()
    event = asyncio.run(AuditRepository(db).record(
        case_id="case-1", action=action, metadata=metadata,
    ))
    return event, db.audit_logs.document


def test_case_created_event_retains_existing_structured_details():
    event, persisted = record("case_created", {
        "source": "adaptive_planner", "priority": "critical", "risk_score": 82,
    })
    assert event["metadata"]["priority"] == "critical"
    assert persisted["metadata"]["risk_score"] == 82


def test_case_status_changed_event_retains_transition_and_actor():
    event, persisted = record("case_status_changed", {
        "from": "new", "to": "reviewing", "analyst_notes": "Start review",
    })
    assert event["metadata"]["from"] == "new"
    assert event["metadata"]["to"] == "reviewing"
    assert persisted["performed_by"]["name"] == "FinGuard AI"


def test_legacy_empty_metadata_remains_backwards_compatible():
    event, persisted = record("case_created", {})
    assert event["metadata"] == {}
    assert persisted["metadata"] == {}
