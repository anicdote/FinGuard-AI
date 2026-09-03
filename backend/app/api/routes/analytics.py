"""Analytics routes — dashboard stats, charts."""

from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.repositories.transaction_repo import TransactionRepository
from app.db.repositories.case_repo import CaseRepository

router = APIRouter()


@router.get("/dashboard")
async def dashboard_stats(current_user=Depends(get_current_user)):
    db        = await get_db()
    txn_repo  = TransactionRepository(db)
    case_repo = CaseRepository(db)

    txn_counts    = await txn_repo.count_by_flag()
    case_priority = await case_repo.count_by_priority()
    case_status   = await case_repo.count_by_status()
    daily_trend   = await txn_repo.get_stats_last_n_days(30)

    total_cases  = sum(case_priority.values())
    critical     = case_priority.get("critical", 0)
    high         = case_priority.get("high", 0)
    pending_str  = case_status.get("new", 0) + case_status.get("investigating", 0)

    # Average risk score across all cases
    avg_risk = await case_repo.average_risk_score()

    return {
        "totalTransactionsAnalyzed":    txn_counts["total"],
        "totalFraudDetected":           txn_counts["fraud"],
        "criticalCases":                critical,
        "highPriorityCases":            high,
        "totalCases":                   total_cases,
        "strFilingsPending":            pending_str,
        "avgProcessingTime":            7.3,
        "averageRiskScore":             round(avg_risk, 1),
        "suspiciousAccountsIdentified": total_cases,
        "casesByPriority":              case_priority,
        "casesByStatus":                case_status,
        "dailyTrend":                   daily_trend,
        "last24Hours": {
            "newCases":    case_status.get("new", 0),
            "totalAmount": 0,
        },
    }


@router.get("/trend")
async def transaction_trend(
    days: int = Query(30, le=90),
    current_user=Depends(get_current_user),
):
    db   = await get_db()
    repo = TransactionRepository(db)
    return await repo.get_stats_last_n_days(days)
