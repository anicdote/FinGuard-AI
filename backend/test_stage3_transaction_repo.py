"""Focused Stage 3 repository tests using in-memory MongoDB."""

import asyncio
import sys
from datetime import datetime, timezone

from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, ".")

from app.db.repositories.transaction_repo import TransactionRepository


UTC = timezone.utc


def at(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


async def main():
    db = AsyncMongoMockClient()["finguard_stage3_repo"]
    repo = TransactionRepository(db)
    target = "ACC-TARGET"

    documents = [
        {"label": "origin", "account_id": target, "counterpartyAccount": "ACC-A", "amount": 100, "timestamp": at(2), "channel": "UPI"},
        {"label": "both", "account_id": target, "counterpartyAccount": target, "amount": 200, "timestamp": at(3), "channel": "NEFT"},
        {"label": "destination", "account_id": "ACC-B", "counterpartyAccount": target, "amount": 300, "timestamp": at(4), "channel": "IMPS"},
        {"label": "outside_window", "account_id": target, "counterpartyAccount": "ACC-C", "amount": 400, "timestamp": at(1), "channel": "RTGS"},
        {"label": "unrelated", "account_id": "ACC-X", "counterpartyAccount": "ACC-Y", "amount": 500, "timestamp": at(5), "channel": "UPI"},
        {"label": "string_id", "id": "TXN-EXCLUDE-1", "account_id": target, "counterpartyAccount": "ACC-D", "amount": 600, "timestamp": at(6), "channel": "UPI"},
    ]
    result = await db.transactions.insert_many(documents)
    ids = dict(zip((doc["label"] for doc in documents), map(str, result.inserted_ids)))

    all_roles = await repo.get_by_account_roles(target)
    assert [doc["label"] for doc in all_roles] == ["string_id", "destination", "both", "origin", "outside_window"]
    assert all(doc["_id"] == ids[doc["label"]] for doc in all_roles)
    assert all_roles[0]["amount"] == 600 and all_roles[0]["channel"] == "UPI"

    bounded = await repo.get_by_account_roles(target, start=at(2), end=at(3))
    assert [doc["label"] for doc in bounded] == ["both", "origin"]

    limited = await repo.get_by_account_roles(target, limit=2)
    assert [doc["label"] for doc in limited] == ["string_id", "destination"]

    excluded = await repo.get_by_account_roles(target, exclude_transaction_id=ids["both"])
    assert [doc["label"] for doc in excluded] == ["string_id", "destination", "origin", "outside_window"]

    string_excluded = await repo.get_by_account_roles(target, exclude_transaction_id="TXN-EXCLUDE-1")
    assert "string_id" not in [doc["label"] for doc in string_excluded]

    # A non-ObjectId string is a valid exclusion input and must not raise.
    non_object_id = await repo.get_by_account_roles(target, exclude_transaction_id="TXN-NOT-PRESENT")
    assert len(non_object_id) == 5

    print("Stage 3 transaction repository tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
