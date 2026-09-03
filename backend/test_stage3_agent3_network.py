"""Focused deterministic tests for Agent 3 network investigation."""

import asyncio
import copy
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from app.services import all_agents
from app.services.all_agents import Agent3Network
from app.services.investigation_context import InvestigationContext


UTC = timezone.utc


def at(day):
    return datetime(2026, 1, day, tzinfo=UTC)


class FixedTransactionRepository:
    """Small repository-shaped fixture; it also verifies focal exclusion."""
    def __init__(self, records):
        self.records = records
        self.calls = []

    async def get_by_account_roles(self, account_id, start=None, end=None, limit=100,
                                   exclude_transaction_id=None):
        self.calls.append((account_id, start, end, limit, exclude_transaction_id))
        return [r for r in self.records
                if str(r["_id"]) != exclude_transaction_id
                and start <= r["timestamp"] <= end
                and (r["account_id"] == account_id or r["counterpartyAccount"] == account_id)][:limit]


async def cyclic_graph_test():
    focal = {"_id": "focal", "account_id": "A", "counterpartyAccount": "B",
             "amount": 10, "timestamp": at(10), "channel": "UPI", "paySimType": "TRANSFER"}
    history = [
        {"_id": "ab-old", "account_id": "A", "counterpartyAccount": "B", "amount": 11, "timestamp": at(8), "channel": "NEFT", "paySimType": "TRANSFER"},
        {"_id": "cb", "account_id": "C", "counterpartyAccount": "B", "amount": 20, "timestamp": at(7), "channel": "IMPS", "paySimType": "TRANSFER"},
        {"_id": "bd", "account_id": "B", "counterpartyAccount": "D", "amount": 30, "timestamp": at(6), "channel": "UPI", "paySimType": "TRANSFER", "is_fraud": 1},
        {"_id": "db", "account_id": "D", "counterpartyAccount": "B", "amount": 40, "timestamp": at(5), "channel": "RTGS", "paySimType": "TRANSFER", "is_fraud": "true"},
        {"_id": "bb-loop", "account_id": "B", "counterpartyAccount": "B", "amount": 5, "timestamp": at(4), "channel": "UPI", "paySimType": "TRANSFER", "fraud_label": "SUSPICIOUS"},
        {"_id": "too-old", "account_id": "A", "counterpartyAccount": "Z", "amount": 99, "timestamp": datetime(2025, 11, 1, tzinfo=UTC), "channel": "UPI", "paySimType": "TRANSFER"},
        focal,
    ]
    repo = FixedTransactionRepository(history)
    agent = Agent3Network(repo)
    ctx = InvestigationContext("focal", focal)
    first = await agent.run(ctx)
    second = await agent.run(InvestigationContext("focal", focal))
    network = first.network

    assert {n["account_id"] for n in network["nodes"]} == {"A", "B", "C", "D"}
    assert {(e["from"], e["to"], e["amount"]) for e in network["edges"]} == {
        ("A", "B", 10.0), ("A", "B", 11.0), ("C", "B", 20.0),
        ("B", "D", 30.0), ("D", "B", 40.0), ("B", "B", 5.0),
    }
    assert all({"timestamp", "channel", "transaction_id"} <= set(e) for e in network["edges"])
    assert all("Z" != n["account_id"] for n in network["nodes"])
    assert isinstance(network["max_pagerank"], float) and network["central_node"] == "B"
    assert any(set(c["account_ids"]) == {"B", "D"} for c in network["scc_clusters"])
    assert network["evidence"]["suspicious_transaction_count"] == 3
    assert network["evidence"]["suspicious_transaction_ratio"] == 0.5
    assert first.network == second.network and first.sub_cases == second.sub_cases
    assert all(case["account_id"] != "A" for case in first.sub_cases)
    assert {case["account_id"] for case in first.sub_cases} == {"B", "D"}
    assert all("Confirmed" not in case["reason"] for case in first.sub_cases)
    assert all(call[4] == "focal" and call[3] == 100 for call in repo.calls)


async def no_history_and_no_cycle_test():
    focal = {"_id": "focal-2", "account_id": "A", "counterpartyAccount": "B",
             "amount": 55, "timestamp": at(10), "channel": "UPI", "paySimType": "TRANSFER"}
    agent = Agent3Network(FixedTransactionRepository([
        {"_id": "bc", "account_id": "B", "counterpartyAccount": "C", "amount": 12, "timestamp": at(9), "channel": "UPI", "paySimType": "TRANSFER"},
    ]))
    ctx = await agent.run(InvestigationContext("focal-2", focal))
    assert ctx.network["node_count"] == 3
    assert all(cluster["node_count"] == 1 for cluster in ctx.network["scc_clusters"])
    empty = await Agent3Network(FixedTransactionRepository([])).run(InvestigationContext("focal-2", focal))
    assert empty.network["node_count"] == 2 and empty.network["edge_count"] == 1


async def labels_do_not_change_network_risk_test():
    focal = {"_id": "focal-labels", "account_id": "A", "counterpartyAccount": "B",
             "amount": 10, "timestamp": at(10), "channel": "UPI", "paySimType": "TRANSFER"}
    behavior = [
        {"_id": "bd", "account_id": "B", "counterpartyAccount": "D", "amount": 30, "timestamp": at(9), "channel": "UPI"},
        {"_id": "db", "account_id": "D", "counterpartyAccount": "B", "amount": 40, "timestamp": at(8), "channel": "RTGS"},
    ]
    labelled = copy.deepcopy(behavior)
    labelled[0]["is_fraud"] = True
    labelled[1]["fraud_label"] = "SUSPICIOUS"
    baseline = await Agent3Network(FixedTransactionRepository(behavior)).run(InvestigationContext("focal-labels", focal))
    changed = await Agent3Network(FixedTransactionRepository(labelled)).run(InvestigationContext("focal-labels", focal))
    assert {n["account_id"]: n["risk_score"] for n in baseline.network["nodes"]} == {
        n["account_id"]: n["risk_score"] for n in changed.network["nodes"]
    }
    assert baseline.sub_cases == changed.sub_cases
    assert baseline.network["evidence"]["provisional_network_risk_score"] == changed.network["evidence"]["provisional_network_risk_score"]
    assert baseline.network["evidence"]["suspicious_transaction_count"] == 0
    assert changed.network["evidence"]["suspicious_transaction_count"] == 2


def suspicious_value_and_legacy_removal_test():
    assert Agent3Network._is_suspicious({"is_fraud": True})
    assert Agent3Network._is_suspicious({"is_fraud": 1})
    assert Agent3Network._is_suspicious({"is_fraud": "true"})
    assert Agent3Network._is_suspicious({"fraud_label": "FrAuD"})
    assert Agent3Network._is_suspicious({"fraud_label": "SUSPICIOUS"})
    assert not Agent3Network._is_suspicious({"is_fraud": "yes"})
    assert not Agent3Network._is_suspicious({"is_fraud": 2})
    assert not hasattr(all_agents, "_LegacyAgent3Network")


async def main():
    suspicious_value_and_legacy_removal_test()
    await cyclic_graph_test()
    await no_history_and_no_cycle_test()
    await labels_do_not_change_network_risk_test()
    print("Stage 3 Agent 3 network tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
