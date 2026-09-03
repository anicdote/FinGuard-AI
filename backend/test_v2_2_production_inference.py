"""Focused production checks for the promoted V2.2 behavioural model."""
import asyncio
import math
from datetime import datetime, timezone

import numpy as np

from app.services.fraud_prediction import V2_2_FEATURES, fraud_service


class FakeTransactionRepository:
    def __init__(self, history):
        self.history = history

    async def get_v2_2_history(self, txn):
        return self.history


def txn(**overrides):
    base = {"id": "test", "account_id": "origin", "counterpartyAccount": "destination", "amount": 100.0,
            "paySimType": "PAYMENT", "timestamp": datetime(2026, 1, 2, 6, tzinfo=timezone.utc), "hour": 6}
    base.update(overrides)
    return base


def assert_result(transaction, history):
    result = fraud_service.score_transaction(transaction, history)
    assert list(result["features"]) == V2_2_FEATURES
    assert len(result["features"]) == 15
    assert all(math.isfinite(v) for v in result["features"].values())
    assert 0 <= result["fraud_probability"] <= 1
    assert result["risk_level"] in {"low", "medium", "high", "critical"}
    return result


def main():
    none = {"origin": {}, "destination": {}}
    # Case 1: no history, including V2.2's ratio=1 default.
    first = assert_result(txn(), none)
    assert first["features"]["origin_txn_count"] == 0 and first["features"]["origin_amount_ratio"] == 1

    # Cases 2, 3, 4, and 8: known prior-only origin/destination summaries.
    history = {"origin": {"count": 2, "average_amount": 75.0, "type_count": 1, "last_marker": 490_000.0},
               "destination": {"count": 3, "average_amount": 50.0, "type_count": 2, "last_marker": 489_998.0}}
    known = txn(amount=150.0, paySimType="TRANSFER", step=490_001)
    result = assert_result(known, history)
    f = result["features"]
    assert np.isclose(f["origin_txn_count"], math.log1p(2))
    assert np.isclose(f["origin_prev_avg_amount"], math.log1p(75.0))
    assert np.isclose(f["origin_amount_ratio"], 2.0)
    assert np.isclose(f["origin_type_frequency"], 0.5)
    assert np.isclose(f["time_since_prev_origin"], math.log1p(1.0))
    assert np.isclose(f["destination_txn_count"], math.log1p(3))
    # The current transaction is absent: count remains exactly the two prior rows.
    assert f["origin_txn_count"] != math.log1p(3)

    # Cases 5, 6, 7: behavioural flags retain V2.2 semantics.
    flags = assert_result(txn(amount=1_000_001, paySimType="CASH_OUT", hour=23), none)["features"]
    assert flags["is_night"] == flags["large_amount"] == flags["is_cash_out"] == 1 and flags["is_transfer"] == 0

    # Async repository integration path returns the same API-compatible schema.
    async_result = asyncio.run(fraud_service.score_transaction_with_history(known, FakeTransactionRepository(history)))
    assert async_result.keys() == result.keys()
    print("V2.2 production inference checks passed (8 cases).")


if __name__ == "__main__":
    main()
