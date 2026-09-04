"""Repository — all fraud case DB operations."""

from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class CaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.cases

    async def create(self, case: dict) -> dict:
        case["created_at"] = datetime.now(timezone.utc)
        case["updated_at"] = datetime.now(timezone.utc)
        result = await self.col.insert_one(case)
        case["_id"] = str(result.inserted_id)
        return case

    async def get_by_id(self, case_id: str) -> Optional[dict]:
        doc = await self.col.find_one({"id": case_id})
        if not doc:
            try:
                doc = await self.col.find_one({"_id": ObjectId(case_id)})
            except Exception:
                pass
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_by_transaction_ids(self, transaction_ids: List[str]) -> Optional[dict]:
        """Return an existing case containing any of the supplied transactions."""
        ids = [str(value) for value in transaction_ids if value is not None]
        if not ids:
            return None
        doc = await self.col.find_one({"transaction_ids": {"$in": ids}})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def update_investigation(self, case_id: str, case_fields: dict) -> Optional[dict]:
        """Refresh AI investigation fields on an existing case without changing human review state."""
        allowed = {
            "priority", "risk_score", "anomaly_score", "fatf_typology",
            "transaction_ids", "suspicious_transactions", "total_amount",
            "evidence_summary", "network_analysis", "str_narrative",
            "investigation", "recommendation", "explanation", "shap_values",
            "agent_log", "sub_cases", "watchlist_hits", "regulatory",
            "confidence_scores",
        }
        update = {key: value for key, value in case_fields.items() if key in allowed}
        update["updated_at"] = datetime.now(timezone.utc)
        result = await self.col.update_one({"id": case_id}, {"$set": update})
        if result.matched_count == 0:
            try:
                result = await self.col.update_one({"_id": ObjectId(case_id)}, {"$set": update})
            except Exception:
                pass
        if result.matched_count == 0:
            return None
        return await self.get_by_id(case_id)

    async def list_all(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_officer_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[dict]:
        query = {}
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if assigned_officer_id:
            query["assigned_officer_id"] = assigned_officer_id
        cursor = self.col.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs

    async def update_status(self, case_id: str, status: str, analyst_notes: str = "") -> bool:
        update = {"$set": {"status": status, "analyst_notes": analyst_notes, "updated_at": datetime.now(timezone.utc)}}
        result = await self.col.update_one({"id": case_id}, update)
        if result.modified_count == 0:
            try:
                result = await self.col.update_one({"_id": ObjectId(case_id)}, update)
            except Exception:
                pass
        return result.modified_count > 0

    async def record_human_review(self, case_id: str, review: dict) -> Optional[dict]:
        now = datetime.now(timezone.utc)
        update = {
            "$set": {"human_review": review, "updated_at": now},
            "$push": {"review_history": review},
        }
        result = await self.col.update_one({"id": case_id}, update)
        if result.modified_count == 0:
            try:
                result = await self.col.update_one({"_id": ObjectId(case_id)}, update)
            except Exception:
                pass
        if result.modified_count == 0:
            return None
        return await self.get_by_id(case_id)

    async def assign_officer(self, case_id: str, officer_id: str, officer_name: str, assigned_by_id: str, assigned_by_name: str) -> Optional[dict]:
        now = datetime.now(timezone.utc)
        update = {"$set": {
            "assigned_officer_id": officer_id,
            "assigned_officer_name": officer_name,
            "assigned_by_id": assigned_by_id,
            "assigned_by_name": assigned_by_name,
            "assigned_at": now,
            "updated_at": now,
        }}
        result = await self.col.update_one({"id": case_id}, update)
        if result.matched_count == 0:
            try:
                result = await self.col.update_one({"_id": ObjectId(case_id)}, update)
            except Exception:
                pass
        if result.matched_count == 0:
            return None
        return await self.get_by_id(case_id)

    async def record_false_positive(self, case_id: str, feedback: dict) -> Optional[dict]:
        now = datetime.now(timezone.utc)
        update = {"$set": {"false_positive": True, "false_positive_feedback": feedback, "updated_at": now}}
        result = await self.col.update_one({"id": case_id}, update)
        if result.matched_count == 0:
            try:
                result = await self.col.update_one({"_id": ObjectId(case_id)}, update)
            except Exception:
                pass
        if result.matched_count == 0:
            return None
        return await self.get_by_id(case_id)

    async def false_positive_stats(self) -> dict:
        total = await self.col.count_documents({})
        false_positives = await self.col.count_documents({"false_positive": True})
        rate = (false_positives / total * 100) if total else 0.0
        pipeline = [
            {"$match": {"false_positive": True}},
            {"$group": {"_id": "$false_positive_feedback.reason", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        reasons = await self.col.aggregate(pipeline).to_list(length=100)
        return {
            "total_cases": total,
            "false_positive_count": false_positives,
            "false_positive_rate": round(rate, 2),
            "top_reasons": [{"reason": item.get("_id") or "Unspecified", "count": item.get("count", 0)} for item in reasons],
        }

    async def count_by_priority(self) -> dict:
        docs = await self.col.aggregate([{"$group": {"_id": "$priority", "count": {"$sum": 1}}}]).to_list(length=10)
        return {d["_id"]: d["count"] for d in docs}

    async def count_by_status(self) -> dict:
        docs = await self.col.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]).to_list(length=10)
        return {d["_id"]: d["count"] for d in docs}

    async def average_risk_score(self) -> float:
        docs = await self.col.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$risk_score"}}}]).to_list(length=1)
        return (docs[0]["avg"] or 0.0) if docs else 0.0
