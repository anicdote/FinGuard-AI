"""Persistence for short-lived authorization challenges, never biometric material."""

from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument


def now() -> datetime:
    return datetime.now(timezone.utc)


def serialise(document: Optional[dict]) -> Optional[dict]:
    if document:
        document["_id"] = str(document["_id"])
    return document


class BiometricChallengeRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.biometric_challenges

    async def create(self, challenge: dict) -> dict:
        challenge["created_at"] = now()
        challenge["updated_at"] = challenge["created_at"]
        result = await self.collection.insert_one(challenge)
        challenge["_id"] = str(result.inserted_id)
        return challenge

    async def get(self, challenge_id: str) -> Optional[dict]:
        return serialise(await self.collection.find_one({"challenge_id": challenge_id}))

    async def update(self, challenge_id: str, fields: dict) -> None:
        fields["updated_at"] = now()
        await self.collection.update_one({"challenge_id": challenge_id}, {"$set": fields})

    async def consume_download(self, challenge_id: str, user_id: str, case_id: str, now_at: datetime) -> bool:
        """Atomically consume exactly one valid STR-download authorization."""
        result = await self.collection.update_one(
            {
                "challenge_id": challenge_id,
                "purpose": "str_download",
                "user_id": user_id,
                "case_id": case_id,
                "status": "success",
                "consumed": False,
                "expires_at": {"$gt": now_at},
            },
            {"$set": {"consumed": True, "consumed_at": now_at, "updated_at": now_at}},
        )
        return result.modified_count == 1

    async def store_login_tokens(self, challenge_id: str, tokens: dict, now_at: datetime) -> Optional[dict]:
        """Store one token pair atomically for retry-safe successful polling."""
        document = await self.collection.find_one_and_update(
            {"challenge_id": challenge_id, "purpose": "login", "status": "success",
             "expires_at": {"$gt": now_at}, "login_tokens": {"$exists": False}},
            {"$set": {"login_tokens": tokens, "completed_at": now_at, "updated_at": now_at}},
            return_document=ReturnDocument.AFTER,
        )
        return serialise(document)
