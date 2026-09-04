"""Regression coverage for Agent 5 draft rendering data."""

import asyncio

from app.services.all_agents import Agent5Explanation
from app.services.investigation_context import InvestigationContext


def test_agent5_str_uses_canonical_account_and_populates_description():
    ctx = InvestigationContext("TXN-123", {
        "account_id": "ACCFVBGIDZR",
        "id": "TXNATN7209V5",
        "amount": 1000,
        "channel": "WIRE",
        "counterparty": "Indo-Gulf Trading Co",
    })
    ctx.anomaly_scores = {"probability": 0.82, "risk_level": "critical"}
    ctx.evidence = {"patterns": ["rapid_movement"]}
    ctx.network = {"node_count": 2}
    ctx.regulatory = {"fatf_typologies": [], "pmla_sections": []}
    ctx.agent_log = [
        {"agent": f"Planner→Agent{number}", "timestamp": ""}
        for number in range(1, 6)
    ]

    asyncio.run(Agent5Explanation().run(ctx))

    assert "Account:      ACCFVBGIDZR" in ctx.str_narrative
    assert "TXNATN7209V5" not in ctx.str_narrative
    assert "Counterparty: Indo-Gulf Trading Co" in ctx.str_narrative
    description = ctx.str_narrative.split("DESCRIPTION:\n", 1)[1].split("\n─", 1)[0]
    assert description == ctx.explanation
    # Planner invocations are not counted as agents, and Agent 6 has not run.
    assert "AGENTS RAN:   5" in ctx.str_narrative
