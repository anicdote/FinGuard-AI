"""Prediction routes — real-time scoring and batch inference."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.core.security import get_current_user
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


class BatchScoringRequest(BaseModel):
    transactions: List[ScoringRequest]


@router.post("/score")
async def score_transaction(
    req: ScoringRequest,
    current_user=Depends(get_current_user),
):
    """Real-time fraud scoring for a single transaction."""
    return fraud_service.score_transaction(req.model_dump())


@router.post("/batch")
async def score_batch(
    req: BatchScoringRequest,
    current_user=Depends(get_current_user),
):
    """Batch scoring for multiple transactions."""
    txns = [t.model_dump() for t in req.transactions]
    return fraud_service.score_batch(txns)


@router.get("/model-info")
async def model_info(current_user=Depends(get_current_user)):
    """Return current model metadata — reflects whichever scorer actually loaded (trained models or rule-based fallback)."""
    return {
        "model_version": MODEL_VERSION,
        "fraud_threshold": 0.65,
        "features": [
            "log_amount", "balance_drain", "near_ctr",
            "is_night", "is_intl", "is_risky_ch", "is_cash_out",
        ],
    }
