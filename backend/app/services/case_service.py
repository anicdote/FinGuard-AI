"""
Case Service
────────────
Creates and manages fraud investigation cases.

The actual investigation is now performed by:
    Adaptive Planner → Agents → InvestigationContext

This service does NOT re-run the investigation.

Its job is to:
    1. Group investigated transactions by account
    2. Extract results from InvestigationContext
    3. Preserve fields expected by the existing frontend
    4. Store the complete investigation in MongoDB
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.core.logging import prediction_logger
from app.db.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)


class CaseService:
    """Creates and manages fraud investigation cases."""

    async def create_cases_from_fraud(
        self,
        fraudulent_txns: List[dict],
        db,
    ) -> List[dict]:
        """
        Group fraud transactions by account and create one case per account.

        Each transaction has already gone through:
            Adaptive Planner → Agents → InvestigationContext

        Therefore this method only persists the investigation results.
        """

        from app.db.repositories.case_repo import CaseRepository

        case_repo = CaseRepository(db)

        # ─────────────────────────────────────────────────────────────
        # Group fraudulent transactions by account
        # ─────────────────────────────────────────────────────────────

        by_account: Dict[str, List[dict]] = defaultdict(list)

        for txn in fraudulent_txns:
            account_id = txn.get(
                "account_id",
                txn.get("accountId", "unknown"),
            )

            by_account[account_id].append(txn)

        new_cases = []

        # ─────────────────────────────────────────────────────────────
        # Create one investigation case per account
        # ─────────────────────────────────────────────────────────────

        for account_id, txns in by_account.items():

            case = self._build_case(
                account_id=account_id,
                txns=txns,
            )

            saved = await case_repo.create(case)

            prediction_logger.log_case_created(
                case_id=saved["_id"],
                account_id=account_id,
                risk_score=case["risk_score"],
            )

            # Phase 10 — persist the completed autonomous investigation and
            # case creation as an immutable audit event.
            audit = AuditRepository(db)
            await audit.record(
                case_id=case["id"],
                action="case_created",
                metadata={
                    "source": "adaptive_planner",
                    "transaction_ids": case.get("transaction_ids", []),
                    "risk_score": case.get("risk_score", 0),
                    "priority": case.get("priority", "unknown"),
                    "recommendation": self._mongo_safe(case.get("recommendation", {})),
                    "agent_count": len(case.get("agent_log", [])),
                    "agent_log": self._mongo_safe(case.get("agent_log", [])),
                },
            )

            new_cases.append(saved)

            logger.info(
                f"[CaseService] Case created: "
                f"{saved['_id']} | "
                f"account={account_id} | "
                f"risk={case['risk_score']:.2f}"
            )

        return new_cases

    # ═══════════════════════════════════════════════════════════════
    # CASE CONSTRUCTION
    # ═══════════════════════════════════════════════════════════════

    def _build_case(
        self,
        account_id: str,
        txns: List[dict],
    ) -> dict:
        """
        Build a persistent case from completed investigations.

        IMPORTANT:
        No ML, evidence gathering, network analysis, regulatory analysis,
        or STR generation happens here anymore.
        """

        # ─────────────────────────────────────────────────────────────
        # Extract completed InvestigationContexts
        # ─────────────────────────────────────────────────────────────

        investigations = []

        for txn in txns:
            ctx = txn.get("investigation_ctx")

            if ctx:
                investigations.append(ctx)

        # InvestigationContext may contain a back-reference to the original
        # transaction (and the transaction contains investigation_ctx), which
        # creates a circular object graph. Never persist that live object graph.
        safe_investigations = [
            self._mongo_safe(ctx)
            for ctx in investigations
        ]

        # Highest-risk investigation becomes the primary investigation.
        primary_ctx = self._select_primary_investigation(
            safe_investigations
        )

        # ─────────────────────────────────────────────────────────────
        # Basic transaction information
        # ─────────────────────────────────────────────────────────────

        amounts = [
            float(txn.get("amount", 0))
            for txn in txns
        ]

        total_amount = sum(amounts)

        # Keep the previous case-level behaviour:
        # average fraud probability across transactions.
        probabilities = [
            float(txn.get("fraud_probability", 0))
            for txn in txns
        ]

        if probabilities:
            fraud_probability = sum(probabilities) / len(probabilities)
        else:
            fraud_probability = 0.0

        fraud_probability = min(
            max(fraud_probability, 0.0),
            1.0,
        )

        risk_score = round(
            fraud_probability * 100,
            2,
        )

        priority = self._priority(risk_score)

        # ─────────────────────────────────────────────────────────────
        # Extract primary investigation results
        # ─────────────────────────────────────────────────────────────

        if primary_ctx:

            anomaly_scores = primary_ctx.get(
                "anomaly_scores",
                {},
            )

            evidence = primary_ctx.get(
                "evidence",
                {},
            )

            watchlist_hits = primary_ctx.get(
                "watchlist_hits",
                [],
            )

            network = primary_ctx.get(
                "network",
                {},
            )

            sub_cases = primary_ctx.get(
                "sub_cases",
                [],
            )

            regulatory = primary_ctx.get(
                "regulatory",
                {},
            )

            shap_values = primary_ctx.get(
                "shap_values",
                [],
            )

            explanation = primary_ctx.get(
                "explanation",
                "",
            )

            str_narrative = primary_ctx.get(
                "str_narrative",
                "",
            )

            recommendation = primary_ctx.get(
                "recommendation",
                {},
            )

            confidence_scores = primary_ctx.get(
                "confidence_scores",
                {},
            )

            agent_log = primary_ctx.get(
                "agent_log",
                [],
            )

            flags = primary_ctx.get(
                "flags",
                {},
            )

            # Agent 4 returns detailed FATF objects.
            # Keep the existing frontend-compatible top-level field
            # as a simple list of typology names.
            fatf_typology = self._extract_typology_names(
                regulatory.get(
                    "fatf_typologies",
                    [],
                )
            )

        else:
            # This should rarely happen because background.py only sends
            # successful planner investigations to CaseService.
            #
            # Keep a safe fallback so the worker never crashes if an
            # older transaction reaches this service.

            anomaly_scores = {
                "probability": fraud_probability,
                "risk_level": self._risk_level(
                    fraud_probability
                ),
            }

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

        # ─────────────────────────────────────────────────────────────
        # Complete investigation object
        # ─────────────────────────────────────────────────────────────

        investigation = {
            "primary_transaction_id": (
                primary_ctx.get("transaction_id")
                if primary_ctx
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

            # Store all individual investigations belonging to this
            # account-level case. These are sanitized so MongoDB never sees
            # circular references from InvestigationContext.
            "transaction_investigations": safe_investigations,
        }

        # ─────────────────────────────────────────────────────────────
        # Persistent MongoDB case
        # ─────────────────────────────────────────────────────────────

        case = {
            # Existing CaseRepository / frontend identifier
            "id": str(uuid.uuid4()),

            # Account
            "account_id": account_id,

            "account_name": txns[0].get(
                "accountName",
                txns[0].get("account_name", "Unknown"),
            ),

            # Existing case workflow
            "status": "new",

            "priority": priority,

            "risk_score": risk_score,

            "anomaly_score": round(
                fraud_probability,
                3,
            ),

            # Existing frontend expects this field.
            "fatf_typology": fatf_typology,

            # Transactions belonging to this case.
            "transaction_ids": [
                txn.get(
                    "_id",
                    txn.get("id"),
                )
                for txn in txns
            ],

            # Transactions may contain investigation_ctx, which can point
            # back to the transaction. Strip that runtime-only field before
            # storing the transaction snapshot in MongoDB.
            "suspicious_transactions": [
                self._mongo_safe(txn)
                for txn in txns
            ],

            "total_amount": total_amount,

            # ─────────────────────────────────────────────────────────
            # Existing frontend-compatible fields
            # ─────────────────────────────────────────────────────────

            "evidence_summary": self._mongo_safe(evidence),

            "network_analysis": self._mongo_safe(network),

            "str_narrative": str_narrative,

            # ─────────────────────────────────────────────────────────
            # New autonomous-investigation fields
            # ─────────────────────────────────────────────────────────

            "investigation": investigation,

            "recommendation": self._mongo_safe(recommendation),

            "explanation": explanation,

            "shap_values": self._mongo_safe(shap_values),

            "agent_log": self._mongo_safe(agent_log),

            "sub_cases": self._mongo_safe(sub_cases),

            "watchlist_hits": self._mongo_safe(watchlist_hits),

            "regulatory": self._mongo_safe(regulatory),

            "confidence_scores": self._mongo_safe(confidence_scores),

            # When the case was created.
            "detected_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        return case

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def _mongo_safe(cls, value, seen=None):
        """
        Convert runtime investigation data into a MongoDB-safe structure.

        InvestigationContext can contain circular references such as:
            transaction -> investigation_ctx -> transaction

        Runtime-only back-references are removed, and any remaining cycle is
        cut instead of allowing PyMongo to recurse indefinitely.
        """
        if seen is None:
            seen = set()

        if value is None or isinstance(
            value,
            (str, int, float, bool, bytes)
        ):
            return value

        # MongoDB-native / date-like values are already serializable by PyMongo.
        if type(value).__module__.startswith("bson") or isinstance(
            value,
            (datetime,)
        ):
            return value

        object_id = id(value)
        if object_id in seen:
            return None

        seen.add(object_id)

        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                # These runtime fields are the likely source of the circular
                # transaction <-> InvestigationContext reference.
                if key in {"investigation_ctx", "transaction", "txn"}:
                    continue

                result[key] = cls._mongo_safe(item, seen.copy())

            return result

        if isinstance(value, list):
            return [
                cls._mongo_safe(item, seen.copy())
                for item in value
            ]

        if isinstance(value, tuple):
            return [
                cls._mongo_safe(item, seen.copy())
                for item in value
            ]

        # Avoid trying to serialize arbitrary Python runtime objects.
        return str(value)


    @staticmethod
    def _select_primary_investigation(
        investigations: List[dict],
    ) -> Optional[dict]:
        """
        Select the highest-risk transaction investigation.

        This becomes the primary investigation displayed at case level.
        """

        if not investigations:
            return None

        return max(
            investigations,
            key=lambda ctx: float(
                ctx.get(
                    "anomaly_scores",
                    {},
                ).get(
                    "probability",
                    0,
                )
            ),
        )

    @staticmethod
    def _extract_typology_names(
        typologies: List[Any],
    ) -> List[str]:
        """
        Convert Agent 4's detailed typology objects into the simple
        list expected by the existing frontend.

        Example:

        {
            "code": "T3_Layering",
            "name": "Layering",
            ...
        }

        becomes:

        ["Layering"]
        """

        names = []

        for typology in typologies:

            if isinstance(typology, dict):

                name = typology.get(
                    "name",
                    typology.get("code"),
                )

                if name:
                    names.append(name)

            elif isinstance(typology, str):

                names.append(typology)

        return names or ["Suspicious Activity"]

    @staticmethod
    def _priority(
        risk_score: float,
    ) -> str:

        if risk_score >= 85:
            return "critical"

        if risk_score >= 65:
            return "high"

        if risk_score >= 40:
            return "medium"

        return "low"

    @staticmethod
    def _risk_level(
        probability: float,
    ) -> str:

        if probability >= 0.85:
            return "critical"

        if probability >= 0.65:
            return "high"

        if probability >= 0.40:
            return "medium"

        return "low"


case_service = CaseService()