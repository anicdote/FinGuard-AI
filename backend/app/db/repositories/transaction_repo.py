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

    async def _v2_2_role_summary(self, field: str, account: str, before: datetime, transaction_type: str) -> dict:
        """Aggregate one account role strictly before ``before`` without loading rows."""
        empty = {"count": 0, "average_amount": 0.0, "type_count": 0, "last_marker": None}
        if not account:
            return empty
        match = {field: account, "timestamp": {"$lt": before}}
        pipeline = [{"$match": match}, {"$group": {"_id": None, "count": {"$sum": 1}, "average_amount": {"$avg": "$amount"}, "type_count": {"$sum": {"$cond": [{"$eq": [{"$toUpper": {"$ifNull": ["$paySimType", "$type"]}}, transaction_type]}, 1, 0]}}}}]
        rows = await self.col.aggregate(pipeline).to_list(length=1)
        if not rows:
            return empty
        last = await self.col.find(match, {"timestamp": 1, "step": 1}).sort("timestamp", -1).limit(1).to_list(length=1)
        last_doc = last[0] if last else {}
        if last_doc.get("step") is not None:
            marker = float(last_doc["step"])
        else:
            timestamp = last_doc.get("timestamp")
            if timestamp and timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            marker = timestamp.timestamp() / 3600.0 if timestamp else None
        row = rows[0]
        return {"count": int(row["count"]), "average_amount": float(row.get("average_amount") or 0), "type_count": int(row.get("type_count", 0)), "last_marker": marker}

    async def get_v2_2_history(self, txn: dict) -> dict:
        """Return V2.2 origin/destination context from records before this transaction."""
        before = txn.get("timestamp") or datetime.now(timezone.utc)
        if isinstance(before, str):
            before = datetime.fromisoformat(before.replace("Z", "+00:00"))
        if before.tzinfo is None:
            before = before.replace(tzinfo=timezone.utc)
        transaction_type = str(txn.get("paySimType", txn.get("type", "PAYMENT"))).upper()
        return {
            "origin": await self._v2_2_role_summary("account_id", txn.get("account_id", txn.get("nameOrig", "")), before, transaction_type),
            "destination": await self._v2_2_role_summary("counterpartyAccount", txn.get("counterpartyAccount", txn.get("nameDest", "")), before, transaction_type),
        }

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
