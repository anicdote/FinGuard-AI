import asyncio
import sys

sys.path.insert(0, ".")

from app.services.all_agents import Agent4Regulatory
from app.services.investigation_context import InvestigationContext


def make_context(
    *,
    fraud_probability=0.10,
    patterns=None,
    evidence_confidence=0.40,
    watchlist_hits=None,
    network=None,
):
    ctx = InvestigationContext(
        transaction_id="TEST-TXN-001",
        transaction={
            "amount": 5000,
            "account_id": "ACC-TEST-001",
            "counterparty": "TEST-COUNTERPARTY",
            "source_of_funds": "salary",
            "beneficial_owner": "TEST-OWNER",
            "transaction_history": ["normal"],
        },
    )

    ctx.anomaly_scores = {
        "xgb_score": fraud_probability,
        "iso_score": fraud_probability,
        "probability": fraud_probability,
    }

    ctx.evidence = {
        "patterns": patterns or [],
        "evidence_confidence": evidence_confidence,
    }

    ctx.watchlist_hits = watchlist_hits or []
    ctx.watchlist_hit = bool(watchlist_hits)

    if network is not None:
        ctx.network = network

    return ctx


async def run_test(name, ctx, expected_status=None):
    result = await Agent4Regulatory().run(ctx)
    regulatory = result.regulatory

    if expected_status:
        actual = regulatory["reportability_assessment"]["status"]
        assert actual == expected_status, (
            f"{name}: expected {expected_status}, got {actual}"
        )

    print(f"PASS: {name}")
    print(f"  Risk: {regulatory.get('overall_risk')}")
    print(f"  Risk score: {regulatory.get('risk_score')}")
    print(
        f"  STR status: "
        f"{regulatory['reportability_assessment']['status']}"
    )
    print()


async def main():
    # 1. Low-risk transaction
    await run_test(
        "Low-risk transaction",
        make_context(
            fraud_probability=0.10,
            evidence_confidence=0.20,
        ),
        "NOT_ENOUGH_EVIDENCE",
    )

    # 2. Structuring pattern
    await run_test(
        "Structuring pattern",
        make_context(
            fraud_probability=0.35,
            patterns=["structuring_near_ctr"],
            evidence_confidence=0.80,
        ),
        "FURTHER_REVIEW_REQUIRED",
    )

    # 3. Network risk
    await run_test(
        "Network risk",
        make_context(
            fraud_probability=0.35,
            evidence_confidence=0.70,
            network={
                "node_count": 8,
                "edge_count": 10,
                "nodes": [],
                "edges": [],
                "scc_clusters": [],
                "max_pagerank": 0.4,
                "central_node": "ACC-TEST-001",
            },
        ),
        "FURTHER_REVIEW_REQUIRED",
    )

    # 4. Multiple independent regulatory signals
    multiple_signal_ctx = make_context(
        fraud_probability=0.60,
        patterns=[
            "structuring_near_ctr",
            "round_amount",
            "high_risk_channel",
            "complete_balance_drain",
        ],
        evidence_confidence=0.90,
        watchlist_hits=["TEST-WATCHLIST-HIT"],
        network={
            "node_count": 8,
            "edge_count": 12,
            "nodes": [],
            "edges": [],
            "scc_clusters": [],
            "max_pagerank": 0.5,
            "central_node": "ACC-TEST-001",
        },
    )

    result = await Agent4Regulatory().run(multiple_signal_ctx)

    print("DEBUG: Multiple regulatory signals")
    print("  watchlist_hit:", result.watchlist_hit)
    print("  watchlist_hits:", result.watchlist_hits)
    print("  matched typologies:")
    for item in result.regulatory["fatf_typologies"]:
        print("   ", item)
    print(
        "  independent signals:",
        sum([
            bool(result.regulatory["fatf_typologies"]),
            result.watchlist_hit,
            result.network.get("node_count", 0) > 5,
        ]),
    )
    print(
        "  reportability:",
        result.regulatory["reportability_assessment"],
    )
    print()

    assert (
        result.regulatory["reportability_assessment"]["status"]
        == "STR_REVIEW_RECOMMENDED"
    )

    print("PASS: Multiple regulatory signals")
    # 5. Incomplete information
    incomplete = make_context(
        fraud_probability=0.40,
        patterns=["structuring_near_ctr"],
        evidence_confidence=0.60,
    )
    incomplete.transaction.pop("source_of_funds", None)
    incomplete.transaction.pop("beneficial_owner", None)
    incomplete.transaction.pop("transaction_history", None)

    await run_test(
        "Incomplete information",
        incomplete,
        "FURTHER_REVIEW_REQUIRED",
    )

    # 6. High fraud probability must NOT automatically mean STR
    await run_test(
        "High fraud probability does not automatically mean STR",
        make_context(
            fraud_probability=0.95,
            evidence_confidence=0.40,
        ),
        "NOT_ENOUGH_EVIDENCE",
    )

    print("ALL AGENT 4 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
