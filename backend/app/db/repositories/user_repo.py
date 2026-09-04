"""Repository — user account operations."""

from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.users

    async def create(self, user: dict) -> dict:
        user["created_at"] = datetime.now(timezone.utc)
        user["is_active"] = True
        result = await self.col.insert_one(user)
        user["_id"] = str(result.inserted_id)
        return user

    async def get_by_email(self, email: str) -> Optional[dict]:
        doc = await self.col.find_one({"email": email})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        try:
            oid = ObjectId(user_id)
        except Exception:
            # Not a valid ObjectId (e.g. malformed input from a client) —
            # treat as "not found" instead of letting bson raise a 500.
            return None
        doc = await self.col.find_one({"_id": oid})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_by_biometric_template(self, fingerprint_id: int) -> Optional[dict]:
        """Find a sensor slot owner without returning biometric material."""
        doc = await self.col.find_one({"biometric_template_id": fingerprint_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def list_by_roles(self, roles: list) -> list:
        """List active users whose role is in the given set (e.g. officers for assignment)."""
        cursor = self.col.find({"role": {"$in": roles}, "is_active": {"$ne": False}})
        docs = await cursor.to_list(length=200)
        for d in docs:
            d["_id"] = str(d["_id"])
            d.pop("hashed_password", None)
            d.pop("biometric_template_id", None)
            d.pop("biometric_enrolled_at", None)
        return docs

    async def set_biometric_template(self, user_id: str, fingerprint_id: int) -> bool:
        """Map a user to a sensor template slot; never stores biometric data."""
        try:
            oid = ObjectId(user_id)
        except Exception:
            return False
        result = await self.col.update_one(
            {"_id": oid},
            {"$set": {
                "biometric_template_id": fingerprint_id,
                "biometric_enrolled_at": datetime.now(timezone.utc),
            }},
        )
        return result.modified_count == 1

    async def ensure_default_admin(self, hashed_password: str):
        """Seed a default admin user if none exists."""
        existing = await self.col.find_one({"role": "admin"})
        if not existing:
            await self.col.insert_one({
                "email": "admin@finguard.ai",
                "hashed_password": hashed_password,
                "role": "admin",
                "name": "System Admin",
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
            })
