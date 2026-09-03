"""Repository pattern — all transaction DB operations in one place."""

from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class TransactionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.transactions

    async def create(self, txn: dict) -> dict:
        txn["created_at"] = datetime.now(timezone.utc)
        result = await self.col.insert_one(txn)
        txn["_id"] = str(result.inserted_id)
        return txn

    async def get_by_id(self, txn_id: str) -> Optional[dict]:
        doc = await self.col.find_one({"_id": ObjectId(txn_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_by_account(self, account_id: str, limit: int = 100) -> List[dict]:
        cursor = self.col.find({"account_id": account_id}).sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def list_recent(self, limit: int = 50, skip: int = 0) -> List[dict]:
        cursor = self.col.find().sort("timestamp", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def list_unanalyzed(self, limit: int = 100) -> List[dict]:
        """Fetch transactions not yet run through the ML model."""
        cursor = self.col.find({"analyzed": {"$ne": True}}).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def mark_analyzed(self, txn_id: str, fraud_probability: float, is_fraud: bool):
        await self.col.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {
                "analyzed": True,
                "fraud_probability": fraud_probability,
                "is_fraud": is_fraud,
                "analyzed_at": datetime.now(timezone.utc),
            }},
        )

    async def reset_analyzed(self, transaction_ids: List[str]) -> int:
        """
        Mark transactions as unanalyzed so the background worker picks them
        back up and re-runs the Adaptive Planner / 6-agent pipeline on them.
        Used by the "request more evidence / reopen investigation" review
        action — the AI re-investigates, the officer does not.
        """
        object_ids = []
        for tid in transaction_ids:
            try:
                object_ids.append(ObjectId(tid))
            except Exception:
                continue
        if not object_ids:
            return 0
        result = await self.col.update_many(
            {"_id": {"$in": object_ids}},
            {"$set": {"analyzed": False}},
        )
        return result.modified_count

    async def count_by_flag(self) -> dict:
        total = await self.col.count_documents({})
        fraud = await self.col.count_documents({"is_fraud": True})
        return {"total": total, "fraud": fraud, "clean": total - fraud}

    async def get_stats_last_n_days(self, days: int = 30) -> List[dict]:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
                "fraud_count": {"$sum": {"$cond": ["$is_fraud", 1, 0]}},
            }},
            {"$sort": {"_id": 1}},
        ]
        return await self.col.aggregate(pipeline).to_list(length=days + 5)
