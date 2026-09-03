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
    ]
    result = await db.transactions.insert_many(documents)
    ids = dict(zip((doc["label"] for doc in documents), map(str, result.inserted_ids)))

    all_roles = await repo.get_by_account_roles(target)
    assert [doc["label"] for doc in all_roles] == ["destination", "both", "origin", "outside_window"]
    assert all(doc["_id"] == ids[doc["label"]] for doc in all_roles)
    assert all_roles[0]["amount"] == 300 and all_roles[0]["channel"] == "IMPS"

    bounded = await repo.get_by_account_roles(target, start=at(2), end=at(3))
    assert [doc["label"] for doc in bounded] == ["both", "origin"]

    limited = await repo.get_by_account_roles(target, limit=2)
    assert [doc["label"] for doc in limited] == ["destination", "both"]

    excluded = await repo.get_by_account_roles(target, exclude_transaction_id=ids["both"])
    assert [doc["label"] for doc in excluded] == ["destination", "origin", "outside_window"]

    print("Stage 3 transaction repository tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
