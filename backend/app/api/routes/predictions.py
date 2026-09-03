"""Prediction routes — real-time scoring and batch inference."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.core.security import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.db.repositories.transaction_repo import TransactionRepository
from app.services.fraud_prediction import fraud_service, MODEL_VERSION

router = APIRouter()


class ScoringRequest(BaseModel):
    account_id: str
    amount: float
    location: str
    channel: str
    paySimType: str = "PAYMENT"
    oldbalanceOrg: float = 0
    newbalanceOrig: float = 0
    hour: int = 12
    description: str = ""
    counterpartyAccount: str = ""
    timestamp: Optional[datetime] = None


class BatchScoringRequest(BaseModel):
    transactions: List[ScoringRequest]


@router.post("/score")
async def score_transaction(
    req: ScoringRequest,
    current_user=Depends(get_current_user),
):
    """Real-time fraud scoring for a single transaction."""
    txn = req.model_dump()
    txn["timestamp"] = txn["timestamp"] or datetime.now(timezone.utc)
    txn["hour"] = txn["timestamp"].hour
    return await fraud_service.score_transaction_with_history(txn, TransactionRepository(await get_db()))


@router.post("/batch")
async def score_batch(
    req: BatchScoringRequest,
    current_user=Depends(get_current_user),
):
    """Batch scoring for multiple transactions."""
    txns = [t.model_dump() for t in req.transactions]
    for txn in txns:
        txn["timestamp"] = txn["timestamp"] or datetime.now(timezone.utc)
        txn["hour"] = txn["timestamp"].hour
    return await fraud_service.score_batch_with_history(txns, TransactionRepository(await get_db()))


@router.get("/model-info")
async def model_info(current_user=Depends(get_current_user)):
    """Return current model metadata — reflects whichever scorer actually loaded (trained models or rule-based fallback)."""
    return {
        "model_version": MODEL_VERSION,
        "fraud_threshold": settings.FRAUD_THRESHOLD,
        "features": list(fraud_service.extract_features({}).keys()),
    }
