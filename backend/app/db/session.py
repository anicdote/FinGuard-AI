"""Async MongoDB connection using Motor driver.
   Swap for SQLAlchemy + asyncpg for PostgreSQL.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_db():
    global _client, _db
    logger.info(f"Connecting to MongoDB: {settings.MONGODB_URL}")
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _db = _client[settings.MONGODB_DB]

    # Ensure indexes
    await _db.transactions.create_index("account_id")
    await _db.transactions.create_index("timestamp")
    await _db.transactions.create_index([("account_id", 1), ("timestamp", -1)])
    await _db.transactions.create_index([("counterpartyAccount", 1), ("timestamp", -1)])
    await _db.transactions.create_index("is_fraud")
    await _db.cases.create_index("account_id")
    await _db.cases.create_index("status")
    await _db.cases.create_index("priority")
    await _db.users.create_index("email", unique=True)
    await _db.users.create_index("biometric_template_id", sparse=True)
    await _db.biometric_challenges.create_index("challenge_id", unique=True)
    await _db.biometric_challenges.create_index("expires_at", expireAfterSeconds=0)
    await _db.predictions.create_index("transaction_id")
    logger.info("MongoDB indexes ensured ✓")


async def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        await init_db()
    return _db


async def close_db():
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")
