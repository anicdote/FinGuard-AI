"""Transaction routes — CRUD + fraud flagging."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.security import get_current_user
from app.db.session import get_db
from app.db.repositories.transaction_repo import TransactionRepository
from app.services.fraud_prediction import fraud_service

router = APIRouter()


class TransactionIn(BaseModel):
    account_id: str
    accountName: str
    amount: float
    currency: str = "INR"
    timestamp: Optional[datetime] = None
    type: str = "debit"
    counterparty: str
    counterpartyAccount: str
    location: str
    channel: str
    description: str = ""
    paySimType: str = "PAYMENT"
    oldbalanceOrg: float = 0
    newbalanceOrig: float = 0
    oldbalanceDest: float = 0
    newbalanceDest: float = 0


@router.post("/", status_code=201)
async def create_transaction(
    txn: TransactionIn,
    current_user=Depends(get_current_user),
):
    db   = await get_db()
    repo = TransactionRepository(db)

    doc = txn.model_dump()
    doc["timestamp"] = doc["timestamp"] or datetime.utcnow()
    doc["hour"] = doc["timestamp"].hour

    # Preliminary score for immediate API response only (UX feedback on submit).
    # This is NOT the final investigation — the transaction still goes through
    # the Adaptive Planner / six-agent pipeline via the background worker.
    # analyzed stays False so the worker's list_unanalyzed() picks it up.
    preliminary = await fraud_service.score_transaction_with_history(doc, repo)
    doc["fraud_probability"] = preliminary["fraud_probability"]
    doc["is_fraud"]          = preliminary["is_fraud"]
    doc["risk_level"]        = preliminary["risk_level"]
    doc["analyzed"]          = False

    saved = await repo.create(doc)
    return saved


@router.get("/")
async def list_transactions(
    limit: int = Query(50, le=200),
    skip: int  = Query(0),
    current_user=Depends(get_current_user),
):
    db   = await get_db()
    repo = TransactionRepository(db)
    return await repo.list_recent(limit=limit, skip=skip)


@router.get("/stats")
async def transaction_stats(current_user=Depends(get_current_user)):
    db   = await get_db()
    repo = TransactionRepository(db)
    counts = await repo.count_by_flag()
    daily  = await repo.get_stats_last_n_days(30)
    return {"counts": counts, "daily": daily}


@router.get("/{txn_id}")
async def get_transaction(txn_id: str, current_user=Depends(get_current_user)):
    db   = await get_db()
    repo = TransactionRepository(db)
    doc  = await repo.get_by_id(txn_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return doc


@router.get("/account/{account_id}")
async def get_account_transactions(
    account_id: str,
    limit: int = Query(100, le=500),
    current_user=Depends(get_current_user),
):
    db   = await get_db()
    repo = TransactionRepository(db)
    return await repo.get_by_account(account_id, limit=limit)
