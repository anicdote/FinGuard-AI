"""Additional regression coverage for Agent 6 edge cases and audit-safe output."""

from app.services.agent6_decision import Agent6Recommend
from app.services.investigation_context import InvestigationContext


def context(**overrides):
    ctx = InvestigationContext("txn-edge", {
        "_id": "txn-edge",
        "account_id": "ACC-EDGE",
        "counterpartyAccount": "ACC-CP",
        "timestamp": "2026-01-01T12:00:00+00:00",
    })
    ctx.anomaly_scores = overrides.get("anomaly", {"probability": 0.2})
    ctx.evidence = overrides.get("evidence", {"evidence_confidence": 0.8, "patterns": []})
    ctx.network = overrides.get("network", {})
    ctx.regulatory = overrides.get("regulatory", {})
    ctx.explanation = overrides.get("explanation", "Agent 5 explanation")
    ctx.str_narrative = overrides.get("str_narrative", "Agent 5 draft")
    ctx.shap_values = overrides.get("shap", [{"feature": "amount", "value": 0.4}])
    ctx.watchlist_hit = overrides.get("watchlist_hit", False)
    ctx.watchlist_hits = overrides.get("watchlist_hits", [])
    ctx.disagreement_flag = overrides.get("disagreement", False)
    return ctx


def decision(ctx):
    return Agent6Recommend().run(ctx).recommendation


def test_high_fraud_without_evidence_does_not_become_confirmation():
    rec = decision(context(
        anomaly={"probability": 0.95},
        evidence={},
        explanation="",
        str_narrative="",
        shap=[],
    ))
    assert rec["action"] == "REQUEST_INFO"
    assert "confirmed" not in rec["reasoning"].lower()


def test_large_low_risk_network_does_not_escalate_by_size():
    rec = decision(context(
        anomaly={"probability": 0.10},
        evidence={"evidence_confidence": 0.90, "patterns": []},
        network={"node_count": 100, "evidence": {"provisional_network_risk_score": 0.10}},
    ))
    assert rec["action"] == "CLOSE"


def test_small_high_risk_network_escalates():
    rec = decision(context(
        anomaly={"probability": 0.20},
        evidence={"evidence_confidence": 0.80, "patterns": []},
        network={"node_count": 3, "evidence": {"provisional_network_risk_score": 0.90}},
    ))
    assert rec["action"] == "ESCALATE"
    assert rec["network_risk_score"] == 0.9


def test_missing_agent4_is_not_interpreted_as_no_regulatory_risk():
    rec = decision(context(
        anomaly={"probability": 0.70},
        evidence={"evidence_confidence": 0.40, "patterns": []},
        regulatory={},
    ))
    assert rec["action"] == "REQUEST_INFO"
    assert any("Agent 4 regulatory assessment is unavailable" in item for item in rec["missing_information"])


def test_missing_agent3_is_explicitly_recorded():
    rec = decision(context(network={}))
    assert any("Agent 3 network investigation is unavailable" in item for item in rec["missing_information"])


def test_str_draft_is_propagated_but_never_marked_filed():
    rec = decision(context(
        regulatory={
            "reportability_assessment": {
                "status": "STR_REVIEW_RECOMMENDED",
                "recommendation": "REVIEW_FOR_STR",
            },
            "str_assessment": {"recommendation": "REVIEW_FOR_STR", "confidence": 0.9},
        },
        str_narrative="DRAFT STR CONTENT",
    ))
    assert rec["agent5_str_draft"] == "DRAFT STR CONTENT"
    assert rec["str_filing_status"] == "not_filed"
    assert rec["case_action"] == "route_to_str_review_not_filed"


def test_missing_values_are_not_converted_to_risk_zero_evidence_claims():
    rec = decision(context(
        anomaly={"probability": None},
        evidence={"evidence_confidence": None},
        network=None,
        regulatory=None,
        explanation=None,
        str_narrative=None,
        shap=[],
    ))
    assert rec["decision"] == "CLOSE"
    assert rec["missing_information"]
    assert rec["decision_basis"] == "deterministic_evidence_aware_synthesis"


def test_model_disagreement_requires_human_review():
    rec = decision(context(
        anomaly={"probability": 0.45},
        evidence={"evidence_confidence": 0.80, "patterns": []},
        disagreement=True,
    ))
    assert rec["action"] == "ESCALATE"
    assert rec["requires_human_review"] is True
    assert any("model disagreement" in item.lower() for item in rec["decision_factors"])


def test_equivalent_customer_identification_gaps_are_deduplicated():
    rec = decision(context(
        regulatory={
            "missing_information": [
                "Customer identification information is not available in the investigation context.",
            ],
        },
    ))
    customer_gaps = [
        item for item in rec["missing_information"]
        if "customer identification information" in item.lower()
    ]
    assert customer_gaps == [
        "Customer identification information is not available in the investigation context.",
    ]
