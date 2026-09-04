"""
Persistence for short-lived biometric challenges.

IMPORTANT:
This repository stores ONLY biometric challenge metadata.
It never stores fingerprint images, fingerprint templates,
or any raw biometric material.
"""

from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


def now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def serialise(document: Optional[dict]) -> Optional[dict]:
    """
    Convert MongoDB's ObjectId into a string for API/application use.
    """
    if document:
        document["_id"] = str(document["_id"])

    return document


class BiometricChallengeRepository:
    """
    MongoDB persistence layer for short-lived biometric challenges.

    Challenge lifecycle:

        pending
           ↓
        finger_required
           ↓
        verifying
           ↓
        success / failed / timeout / hardware_error
           ↓
        consumed

    The actual fingerprint template remains inside the R307S/Arduino
    hardware. This collection contains only challenge metadata.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
    ):
        self.collection = db.biometric_challenges

    # ─────────────────────────────────────────────────────────────────────────
    # Create
    # ─────────────────────────────────────────────────────────────────────────

    async def create(
        self,
        challenge: dict,
    ) -> dict:
        """
        Create a new biometric challenge.
        """

        created_at = now()

        challenge["created_at"] = created_at
        challenge["updated_at"] = created_at

        result = await self.collection.insert_one(
            challenge
        )

        challenge["_id"] = str(
            result.inserted_id
        )

        return challenge

    # ─────────────────────────────────────────────────────────────────────────
    # Get
    # ─────────────────────────────────────────────────────────────────────────

    async def get(
        self,
        challenge_id: str,
    ) -> Optional[dict]:
        """
        Retrieve a biometric challenge by its opaque challenge ID.
        """

        document = await self.collection.find_one(
            {
                "challenge_id": challenge_id,
            }
        )

        return serialise(document)

    # ─────────────────────────────────────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────────────────────────────────────

    async def update(
        self,
        challenge_id: str,
        fields: dict,
    ) -> None:
        """
        Update challenge state and automatically refresh updated_at.
        """

        fields["updated_at"] = now()

        await self.collection.update_one(
            {
                "challenge_id": challenge_id,
            },
            {
                "$set": fields,
            },
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Consume
    # ─────────────────────────────────────────────────────────────────────────

    async def consume(
        self,
        challenge_id: str,
    ) -> bool:
        """
        Atomically consume a successfully completed challenge.

        A successful biometric challenge must only be usable once.

        The update succeeds only when:
            - challenge_id matches
            - status is success
            - consumed is False

        Returns:
            True  -> this request successfully consumed the challenge
            False -> challenge was already consumed or is not successful
        """

        current_time = now()

        result = await self.collection.update_one(
            {
                "challenge_id": challenge_id,
                "status": "success",
                "consumed": False,
            },
            {
                "$set": {
                    "consumed": True,
                    "consumed_at": current_time,
                    "updated_at": current_time,
                }
            },
        )

        return result.modified_count == 1