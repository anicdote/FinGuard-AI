"""Repository for immutable, read-only investigation audit records."""

from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class AuditRepository:
    """Append-only audit log. There are intentionally no update/delete methods."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.audit_logs

    async def record(
        self,
        *,
        case_id: str,
        action: str,
        performed_by: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        actor = performed_by or {
            "id": "system",
            "name": "FinGuard AI",
            "role": "system",
        }
        doc = {
            "case_id": str(case_id),
            "action": action,
            "performed_by": {
                "id": str(actor.get("id", "system")),
                "name": actor.get("name", "FinGuard AI"),
                "role": actor.get("role", "system"),
            },
            "timestamp": now,
            "metadata": metadata or {},
        }
        result = await self.col.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    async def list_for_case(
        self,
        case_id: str,
        *,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict]:
        cursor = (
            self.col.find({"case_id": str(case_id)})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs
