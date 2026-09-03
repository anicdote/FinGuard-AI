"""
Background Worker — Continuous Transaction Analysis
Uses Adaptive Planner + 7-agent pipeline instead of old rule-based scoring.
"""

import asyncio
import logging

from app.core.config import settings
from app.db.session import get_db
from app.db.repositories.transaction_repo import TransactionRepository
from app.services.fraud_prediction import fraud_service
from app.services.case_service import case_service
from app.services.investigation_context import InvestigationContext
from app.services.adaptive_planner import get_planner

logger = logging.getLogger("finguard.worker")


async def analyze_pending_transactions():
    """Single analysis cycle — fetch → full agent pipeline → persist → case creation."""
    try:
        db       = await get_db()
        txn_repo = TransactionRepository(db)

        unanalyzed = await txn_repo.list_unanalyzed(limit=50)
        if not unanalyzed:
            return

        logger.info(f"[Worker] Investigating {len(unanalyzed)} transactions via Adaptive Planner...")
        planner    = get_planner(txn_repo)
        fraud_txns = []

        for txn in unanalyzed:
            txn_id = str(txn.get("_id", txn.get("id", "unknown")))

            try:
                # Agent 1 consumes strict-prior V2.2 behavioural context.
                txn["_behavioral_history"] = await txn_repo.get_v2_2_history(txn)
                # Run full 7-agent pipeline
                ctx = InvestigationContext(txn_id, txn)
                ctx = await planner.investigate(ctx)

                # Mark transaction as analyzed
                await txn_repo.mark_analyzed(
                    txn["_id"],
                    fraud_probability = ctx.fraud_probability,
                    is_fraud          = ctx.fraud_probability >= settings.FRAUD_THRESHOLD,
                )

                # If fraud — attach full investigation context and queue for case creation
                if ctx.fraud_probability >= settings.FRAUD_THRESHOLD:
                    txn["fraud_probability"]  = ctx.fraud_probability
                    txn["investigation_ctx"]  = ctx.to_dict()
                    txn["recommendation"]     = ctx.recommendation
                    txn["shap_values"]        = ctx.shap_values
                    txn["agent_log"]          = ctx.agent_log
                    txn["sub_cases"]          = ctx.sub_cases
                    txn["watchlist_hits"]      = ctx.watchlist_hits
                    txn["fatf_typologies"]    = ctx.regulatory.get("fatf_typologies", [])
                    txn["str_narrative"]      = ctx.str_narrative
                    txn["explanation"]        = ctx.explanation

                    if "account_id" not in txn and "accountId" in txn:
                        txn["account_id"] = txn["accountId"]

                    fraud_txns.append(txn)

                    logger.info(
                        f"[Worker] {txn_id} — {ctx.risk_level.upper()} "
                        f"({ctx.fraud_probability:.1%}) — "
                        f"RECOMMEND: {ctx.recommendation.get('action','?')} "
                        f"({ctx.recommendation.get('confidence_pct',0)}%)"
                    )

            except Exception as e:
                logger.error(f"[Worker] Pipeline failed for {txn_id}: {e}", exc_info=True)
                # Fallback to simple score so transaction doesn't get stuck
                result = fraud_service.score_transaction(txn)
                await txn_repo.mark_analyzed(
                    txn["_id"],
                    fraud_probability = result["fraud_probability"],
                    is_fraud          = result["is_fraud"],
                )

        if fraud_txns:
            logger.info(f"[Worker] {len(fraud_txns)} fraud txns → creating cases...")
            new_cases = await case_service.create_cases_from_fraud(fraud_txns, db)
            logger.info(f"[Worker] Created {len(new_cases)} new case(s)")

    except Exception as e:
        logger.error(f"[Worker] Analysis cycle failed: {e}", exc_info=True)


async def _run_loop():
    logger.info(f"[Worker] Starting — interval: {settings.BATCH_ANALYSIS_INTERVAL_SEC}s")
    while True:
        await analyze_pending_transactions()
        await asyncio.sleep(settings.BATCH_ANALYSIS_INTERVAL_SEC)


async def start_background_worker() -> asyncio.Task:
    task = asyncio.create_task(_run_loop())
    logger.info("[Worker] Background task scheduled ✓")
    return task
