"""Case persistence for completed Adaptive Planner investigations.

CaseService does not investigate transactions. It persists Agent 1–6 output and
updates an existing case when the same transaction is re-investigated.
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.logging import prediction_logger
from app.db.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)


class CaseService:
    """Create/update account-level cases from completed investigations."""

    async def create_cases_from_fraud(self, fraudulent_txns: List[dict], db) -> List[dict]:
        from app.db.repositories.case_repo import CaseRepository

        case_repo = CaseRepository(db)
        by_account: Dict[str, List[dict]] = defaultdict(list)
        for txn in fraudulent_txns:
            account_id = txn.get("account_id", txn.get("accountId", "unknown"))
            by_account[str(account_id)].append(txn)

        results = []
        audit = AuditRepository(db)

        for account_id, txns in by_account.items():
            case = self._build_case(account_id, txns)
            transaction_ids = case.get("transaction_ids", [])

            # Re-running an investigation (for example after a human requests
            # more evidence) must refresh the existing case rather than create
            # an uncontrolled duplicate.
            existing = await case_repo.find_by_transaction_ids(transaction_ids)
            if existing:
                updated = await case_repo.update_investigation(existing["id"], case)
                if updated:
                    await audit.record(
                        case_id=existing["id"],
                        action="case_updated",
                        metadata={
                            "source": "adaptive_planner",
                            "transaction_ids": transaction_ids,
                            "priority": case.get("priority", "unknown"),
                            "decision": (case.get("recommendation") or {}).get("decision"),
                            "recommendation": self._mongo_safe(case.get("recommendation", {})),
                            "agent_count": len(case.get("agent_log", [])),
                        },
                    )
                    results.append(updated)
                    logger.info(
                        "[CaseService] Updated existing case %s for account=%s",
                        existing["id"], account_id,
                    )
                    continue

            saved = await case_repo.create(case)
            prediction_logger.log_case_created(
                case_id=saved["_id"],
                account_id=account_id,
                risk_score=case["risk_score"],
            )
            await audit.record(
                case_id=case["id"],
                action="case_created",
                metadata={
                    "source": "adaptive_planner",
                    "transaction_ids": transaction_ids,
                    "risk_score": case.get("risk_score", 0),
                    "priority": case.get("priority", "unknown"),
                    "decision": (case.get("recommendation") or {}).get("decision"),
                    "recommendation": self._mongo_safe(case.get("recommendation", {})),
                    "agent_count": len(case.get("agent_log", [])),
                    "agent_log": self._mongo_safe(case.get("agent_log", [])),
                },
            )
            results.append(saved)
            logger.info(
                "[CaseService] Created case %s for account=%s priority=%s",
                saved["_id"], account_id, case.get("priority"),
            )

        return results

    def _build_case(self, account_id: str, txns: List[dict]) -> dict:
        investigations = [txn.get("investigation_ctx") for txn in txns if txn.get("investigation_ctx")]
        safe_investigations = [self._mongo_safe(ctx) for ctx in investigations]
        primary_ctx = self._select_primary_investigation(safe_investigations)

        amounts = [self._safe_float(txn.get("amount"), 0.0) for txn in txns]
        probabilities = [
            self._safe_float(txn.get("fraud_probability"), 0.0)
            for txn in txns
            if txn.get("fraud_probability") is not None
        ]
        fraud_probability = self._clamp(sum(probabilities) / len(probabilities)) if probabilities else 0.0

        if primary_ctx:
            anomaly_scores = primary_ctx.get("anomaly_scores", {})
            evidence = primary_ctx.get("evidence", {})
            watchlist_hits = primary_ctx.get("watchlist_hits", [])
            network = primary_ctx.get("network", {})
            sub_cases = primary_ctx.get("sub_cases", [])
            regulatory = primary_ctx.get("regulatory", {})
            shap_values = primary_ctx.get("shap_values", [])
            explanation = primary_ctx.get("explanation", "")
            str_narrative = primary_ctx.get("str_narrative", "")
            recommendation = primary_ctx.get("recommendation", {})
            confidence_scores = primary_ctx.get("confidence_scores", {})
            agent_log = primary_ctx.get("agent_log", [])
            flags = primary_ctx.get("flags", {})
            fatf_typology = self._extract_typology_names(regulatory.get("fatf_typologies", []))
        else:
            anomaly_scores = {"probability": fraud_probability, "risk_level": self._risk_level(fraud_probability)}
            evidence = {}
            watchlist_hits = []
            network = {}
            sub_cases = []
            regulatory = {}
            shap_values = []
            explanation = ""
            str_narrative = ""
            recommendation = {}
            confidence_scores = {}
            agent_log = []
            flags = {}
            fatf_typology = ["Suspicious Activity"]

        # Agent 6 priority is operational and evidence-aware. Fall back to the
        # legacy fraud-derived priority only for old/partial contexts.
        priority = str(recommendation.get("priority") or self._priority(fraud_probability * 100)).lower()
        if priority not in {"low", "medium", "high", "critical"}:
            priority = self._priority(fraud_probability * 100)

        investigation = {
            "primary_transaction_id": (
                primary_ctx.get("transaction_id") if primary_ctx
                else txns[0].get("_id", txns[0].get("id"))
            ),
            "anomaly_scores": anomaly_scores,
            "evidence": evidence,
            "watchlist_hits": watchlist_hits,
            "network": network,
            "sub_cases": sub_cases,
            "regulatory": regulatory,
            "shap_values": shap_values,
            "explanation": explanation,
            "str_narrative": str_narrative,
            "recommendation": recommendation,
            "confidence_scores": confidence_scores,
            "agent_log": agent_log,
            "flags": flags,
            "transaction_investigations": safe_investigations,
        }

        # Preserve risk_score/anomaly_score semantics expected by the existing
        # dashboard while exposing Agent 6's operational priority separately.
        case = {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "account_name": txns[0].get("accountName", txns[0].get("account_name", "Unknown")),
            "status": "new",
            "priority": priority,
            "risk_score": round(fraud_probability * 100, 2),
            "anomaly_score": round(fraud_probability, 3),
            "fatf_typology": fatf_typology,
            "transaction_ids": [txn.get("_id", txn.get("id")) for txn in txns],
            "suspicious_transactions": [self._mongo_safe(txn) for txn in txns],
            "total_amount": sum(amounts),
            "evidence_summary": self._mongo_safe(evidence),
            "network_analysis": self._mongo_safe(network),
            "str_narrative": str_narrative,
            "investigation": investigation,
            "recommendation": self._mongo_safe(recommendation),
            "decision": recommendation.get("decision", recommendation.get("action")),
            "decision_category": recommendation.get("decision_category"),
            "case_action": recommendation.get("case_action"),
            "requires_human_review": recommendation.get("requires_human_review", True),
            "missing_information": self._mongo_safe(recommendation.get("missing_information", [])),
            "str_status": recommendation.get("str_status", "UNAVAILABLE"),
            "str_filing_status": "not_filed",
            "explanation": explanation,
            "shap_values": self._mongo_safe(shap_values),
            "agent_log": self._mongo_safe(agent_log),
            "sub_cases": self._mongo_safe(sub_cases),
            "watchlist_hits": self._mongo_safe(watchlist_hits),
            "regulatory": self._mongo_safe(regulatory),
            "confidence_scores": self._mongo_safe(confidence_scores),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        return case

    @classmethod
    def _mongo_safe(cls, value, seen=None):
        if seen is None:
            seen = set()
        if value is None or isinstance(value, (str, int, float, bool, bytes)):
            return value
        if type(value).__module__.startswith("bson") or isinstance(value, datetime):
            return value
        object_id = id(value)
        if object_id in seen:
            return None
        seen.add(object_id)
        if isinstance(value, dict):
            return {
                key: cls._mongo_safe(item, seen.copy())
                for key, item in value.items()
                if key not in {"investigation_ctx", "transaction", "txn"}
            }
        if isinstance(value, (list, tuple)):
            return [cls._mongo_safe(item, seen.copy()) for item in value]
        return str(value)

    @staticmethod
    def _select_primary_investigation(investigations: List[dict]) -> Optional[dict]:
        if not investigations:
            return None
        return max(
            investigations,
            key=lambda ctx: CaseService._safe_float(
                ctx.get("anomaly_scores", {}).get("probability"), 0.0
            ),
        )

    @staticmethod
    def _extract_typology_names(typologies: List[Any]) -> List[str]:
        names = []
        for typology in typologies:
            if isinstance(typology, dict):
                name = typology.get("name", typology.get("code"))
                if name:
                    names.append(str(name))
            elif isinstance(typology, str):
                names.append(typology)
        return names or ["Suspicious Activity"]

    @staticmethod
    def _safe_float(value, default=0.0) -> float:
        try:
            number = float(value)
            return number if number == number else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float) -> float:
        return min(max(value, 0.0), 1.0)

    @staticmethod
    def _priority(risk_score: float) -> str:
        if risk_score >= 85:
            return "critical"
        if risk_score >= 65:
            return "high"
        if risk_score >= 40:
            return "medium"
        return "low"

    @staticmethod
    def _risk_level(probability: float) -> str:
        if probability >= 0.85:
            return "critical"
        if probability >= 0.65:
            return "high"
        if probability >= 0.40:
            return "medium"
        return "low"


case_service = CaseService()
