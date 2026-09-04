"""Agent 6 — deterministic operational decision and case-management synthesis.

Agent 6 does not investigate. It consumes InvestigationContext produced by
Agents 1–5 and turns those findings into an auditable operational decision.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.services.investigation_context import InvestigationContext


class Agent6Recommend:
    """Synthesize upstream findings into a transparent operational decision."""

    WEIGHTS = {
        "fraud_probability": 0.30,
        "evidence_confidence": 0.20,
        "network_risk": 0.15,
        "regulatory_risk": 0.20,
        "watchlist": 0.10,
        "str_review": 0.05,
    }

    def run(self, ctx: InvestigationContext) -> InvestigationContext:
        fraud = self._number(ctx.anomaly_scores.get("probability"))
        evidence = self._number(ctx.evidence.get("evidence_confidence"))
        network = self._dict(ctx.network)
        network_evidence = self._dict(network.get("evidence"))
        network_risk = self._number(network_evidence.get("provisional_network_risk_score"))
        regulatory = self._dict(ctx.regulatory)
        reportability = self._dict(regulatory.get("reportability_assessment"))
        str_assessment = self._dict(regulatory.get("str_assessment"))
        reportability_status = self._text(reportability.get("status"))
        str_recommendation = self._text(
            str_assessment.get("recommendation") or reportability.get("recommendation")
        )
        regulatory_risk = self._number(regulatory.get("risk_score"))
        watchlist_hit = bool(ctx.watchlist_hit or ctx.watchlist_hits)
        disagreement = bool(ctx.disagreement_flag)
        patterns = self._list(ctx.evidence.get("patterns"))
        missing = self._missing_information(ctx, regulatory)

        action, category = self._decide(
            fraud, evidence, network_risk, regulatory_risk, watchlist_hit,
            disagreement, reportability_status, str_recommendation,
        )
        priority = self._priority(
            fraud, evidence, network_risk, regulatory_risk, watchlist_hit,
            disagreement, reportability_status, missing,
        )
        operational_score = self._operational_score(
            fraud_probability=fraud,
            evidence_confidence=evidence,
            network_risk=network_risk,
            regulatory_risk=regulatory_risk,
            watchlist=watchlist_hit,
            str_review=reportability_status == "STR_REVIEW_RECOMMENDED",
        )
        factors = self._factors(
            fraud, evidence, network_risk, regulatory_risk, watchlist_hit,
            disagreement, reportability_status, str_recommendation, patterns,
        )
        requires_human_review = (
            action != "CLOSE"
            or bool(missing)
            or disagreement
            or reportability_status in {"STR_REVIEW_RECOMMENDED", "FURTHER_REVIEW_REQUIRED"}
        )
        confidence = self._confidence(
            fraud, evidence, network_risk, regulatory_risk, disagreement,
            missing, reportability_status,
        )
        reasoning = self._reasoning(
            action, priority, category, factors, missing,
            bool(ctx.explanation), bool(ctx.str_narrative),
        )

        # Preserve the legacy set_recommendation contract, then add structured
        # fields for case management without changing existing consumers.
        ctx.set_recommendation(
            action,
            confidence,
            reasoning,
            self._regulatory_basis(regulatory),
        )
        ctx.recommendation.update({
            "decision": action,
            "decision_category": category,
            "priority": priority,
            "operational_risk_score": operational_score,
            "decision_factors": factors,
            "supporting_evidence": self._supporting_evidence(ctx),
            "regulatory_assessment": self._regulatory_snapshot(regulatory),
            "str_assessment": self._str_assessment_snapshot(regulatory),
            "str_status": self._str_status(reportability_status, str_recommendation),
            "agent5_explanation": self._text(ctx.explanation),
            "agent5_str_draft": self._text(ctx.str_narrative),
            "missing_information": missing,
            "requires_human_review": requires_human_review,
            "case_action": self._case_action(action),
        })
        return ctx

    def _decide(
        self,
        fraud: Optional[float],
        evidence: Optional[float],
        network_risk: Optional[float],
        regulatory_risk: Optional[float],
        watchlist_hit: bool,
        disagreement: bool,
        reportability_status: str,
        str_recommendation: str,
    ) -> Tuple[str, str]:
        # Agent 4 owns regulatory interpretation. Agent 6 only routes its
        # existing recommendation and never manufactures an STR conclusion.
        if reportability_status == "STR_REVIEW_RECOMMENDED":
            return "FILE_STR", "STR_REVIEW"
        if reportability_status == "FURTHER_REVIEW_REQUIRED":
            if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
                return "BLOCK", "ESCALATE_FOR_REVIEW"
            return "REQUEST_INFO", "FURTHER_REVIEW"
        if reportability_status == "NOT_ENOUGH_EVIDENCE":
            if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
                return "BLOCK", "HIGH_RISK_REVIEW"
            if self._at_least(fraud, .65) and evidence is not None and evidence < .65:
                return "REQUEST_INFO", "EVIDENCE_LIMITED_REVIEW"

        # A watchlist hit becomes a blocking workflow only when supported by
        # both model signal and evidence strength; the hit alone is not proof.
        if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
            return "BLOCK", "HIGH_RISK_REVIEW"

        # High model probability with weak evidence requires more review; it
        # must not be treated as confirmed fraud or an automatic STR.
        if self._at_least(fraud, .85) and evidence is not None and evidence < .65:
            return "REQUEST_INFO", "EVIDENCE_LIMITED_REVIEW"
        if self._at_least(fraud, .85) and (evidence is None or evidence >= .65):
            return "ESCALATE", "HIGH_RISK_REVIEW"
        if self._at_least(network_risk, .65) and (evidence is None or evidence >= .65):
            return "ESCALATE", "NETWORK_RISK_REVIEW"
        if disagreement and self._at_least(fraud, .40):
            return "ESCALATE", "MODEL_DISAGREEMENT_REVIEW"
        if self._at_least(fraud, .65) and evidence is not None and evidence < .65:
            return "REQUEST_INFO", "EVIDENCE_LIMITED_REVIEW"
        if (
            self._at_least(fraud, .50)
            or self._at_least(network_risk, .40)
            or self._at_least(regulatory_risk, .55)
        ):
            return "ESCALATE", "MULTI_SIGNAL_REVIEW"
        if self._at_least(fraud, .35):
            return "MONITOR", "MONITORING"
        if (
            self._at_least(fraud, .20)
            or (evidence is not None and evidence < .50)
            or str_recommendation == "FURTHER_REVIEW"
        ):
            return "REQUEST_INFO", "INFORMATION_REVIEW"
        return "CLOSE", "NO_ACTION"

    def _priority(
        self,
        fraud: Optional[float],
        evidence: Optional[float],
        network_risk: Optional[float],
        regulatory_risk: Optional[float],
        watchlist_hit: bool,
        disagreement: bool,
        reportability_status: str,
        missing: List[str],
    ) -> str:
        if reportability_status == "STR_REVIEW_RECOMMENDED":
            return "critical"
        if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
            return "critical"
        if disagreement or self._at_least(network_risk, .65):
            return "high"
        if self._at_least(fraud, .65) or self._at_least(regulatory_risk, .55):
            return "high"
        if self._at_least(fraud, .35) or (evidence is not None and evidence < .50):
            return "medium"
        if missing:
            return "medium"
        return "low"

    def _operational_score(self, **values: Any) -> float:
        available = []
        for name, weight in self.WEIGHTS.items():
            value = values.get(name)
            if value is None:
                continue
            numeric = float(bool(value)) if name in {"watchlist", "str_review"} else self._clamp(value)
            available.append((numeric, weight))
        if not available:
            return 0.0
        total_weight = sum(weight for _, weight in available)
        return round(sum(value * weight for value, weight in available) / total_weight, 4)

    def _factors(
        self,
        fraud: Optional[float],
        evidence: Optional[float],
        network_risk: Optional[float],
        regulatory_risk: Optional[float],
        watchlist_hit: bool,
        disagreement: bool,
        reportability_status: str,
        str_recommendation: str,
        patterns: List[Any],
    ) -> List[str]:
        factors = []
        if fraud is not None:
            factors.append(f"Agent 1 fraud probability={fraud:.3f}.")
        if evidence is not None:
            factors.append(f"Agent 2 evidence confidence={evidence:.3f}.")
        if patterns:
            factors.append("Observed patterns: " + ", ".join(sorted(str(p) for p in patterns)) + ".")
        if network_risk is not None:
            factors.append(f"Agent 3 provisional network risk={network_risk:.3f}; network size is contextual, not the primary risk signal.")
        if regulatory_risk is not None:
            factors.append(f"Agent 4 regulatory risk score={regulatory_risk:.3f}.")
        if watchlist_hit:
            factors.append("Agent 2 reports one or more watchlist/PEP hits.")
        if disagreement:
            factors.append("Agent 1 reports model disagreement; human review is required.")
        if reportability_status:
            factors.append(f"Agent 4 reportability assessment={reportability_status}.")
        if str_recommendation:
            factors.append(f"Agent 4 STR assessment={str_recommendation}.")
        return factors

    def _reasoning(
        self,
        action: str,
        priority: str,
        category: str,
        factors: List[str],
        missing: List[str],
        has_explanation: bool,
        has_str_draft: bool,
    ) -> str:
        parts = [f"{action}: priority={priority}; category={category}."] + factors
        if missing:
            parts.append("Missing information limits confidence: " + " ".join(missing))
        if has_explanation:
            parts.append("Agent 5 explanation is available for investigator review.")
        if has_str_draft:
            parts.append("Agent 5 STR output is treated as a draft/recommendation only; it does not indicate that an STR has been filed.")
        return " ".join(parts)

    def _confidence(
        self,
        fraud: Optional[float],
        evidence: Optional[float],
        network_risk: Optional[float],
        regulatory_risk: Optional[float],
        disagreement: bool,
        missing: List[str],
        reportability_status: str,
    ) -> float:
        score = self._operational_score(
            fraud_probability=fraud,
            evidence_confidence=evidence,
            network_risk=network_risk,
            regulatory_risk=regulatory_risk,
            watchlist=None,
            str_review=reportability_status == "STR_REVIEW_RECOMMENDED",
        )
        if disagreement:
            score *= .85
        score -= min(.15, .03 * len(missing))
        if reportability_status == "NOT_ENOUGH_EVIDENCE":
            score = min(score, .55)
        return round(max(.20, min(score, .99)), 4)

    def _missing_information(self, ctx: InvestigationContext, regulatory: Dict[str, Any]) -> List[str]:
        result = []
        for item in self._list(regulatory.get("missing_information")):
            text = self._text(item)
            if text and text not in result:
                result.append(text)
        txn = ctx.transaction if isinstance(ctx.transaction, dict) else {}
        if not txn.get("customer_id") and not txn.get("customerId"):
            result.append("Customer identification information is unavailable in the current investigation context.")
        if not txn.get("account_id") and not txn.get("accountId"):
            result.append("Account identification information is unavailable in the current investigation context.")
        if not txn.get("counterparty") and not txn.get("nameDest") and not txn.get("counterpartyAccount"):
            result.append("Counterparty information is unavailable in the current investigation context.")
        if not txn.get("timestamp"):
            result.append("Transaction timestamp is unavailable in the current investigation context.")
        if not ctx.network:
            result.append("Network investigation information is unavailable because Agent 3 did not provide network data.")
        if not regulatory:
            result.append("Regulatory assessment is unavailable because Agent 4 did not provide regulatory data.")
        return self._dedupe(result)

    def _supporting_evidence(self, ctx: InvestigationContext) -> List[Any]:
        regulatory_evidence = self._list(ctx.regulatory.get("supporting_evidence"))
        if regulatory_evidence:
            return regulatory_evidence
        result = []
        if ctx.evidence:
            result.append({"source": "Agent2_Evidence", "items": ctx.evidence})
        if ctx.network:
            result.append({"source": "Agent3_Network", "items": self._dict(ctx.network.get("evidence"))})
        return result

    def _regulatory_snapshot(self, regulatory: Dict[str, Any]) -> Dict[str, Any]:
        keys = (
            "overall_risk", "risk_score", "regulatory_references", "reportability_assessment",
            "primary_typology", "fatf_typologies", "pmla_sections", "supporting_evidence",
            "missing_information", "rationale", "assessment_scope",
        )
        return {key: regulatory[key] for key in keys if key in regulatory}

    def _str_assessment_snapshot(self, regulatory: Dict[str, Any]) -> Dict[str, Any]:
        value = self._dict(regulatory.get("str_assessment"))
        if value:
            return value
        reportability = self._dict(regulatory.get("reportability_assessment"))
        return {
            key: reportability[key]
            for key in ("recommendation", "confidence")
            if key in reportability
        }

    @staticmethod
    def _str_status(status: str, recommendation: str) -> str:
        if status == "STR_REVIEW_RECOMMENDED":
            return "REVIEW_RECOMMENDED"
        if status == "FURTHER_REVIEW_REQUIRED":
            return "FURTHER_REVIEW"
        if status == "NOT_ENOUGH_EVIDENCE":
            return "NOT_ENOUGH_EVIDENCE"
        return recommendation or "UNAVAILABLE"

    @staticmethod
    def _case_action(action: str) -> str:
        return {
            "CLOSE": "close_or_no_action",
            "MONITOR": "monitor",
            "REQUEST_INFO": "request_additional_information",
            "ESCALATE": "escalate_for_human_review",
            "BLOCK": "block_pending_human_review",
            "FILE_STR": "route_to_str_review_not_filed",
        }.get(action, "human_review")

    def _regulatory_basis(self, regulatory: Dict[str, Any]) -> str:
        refs = self._list(regulatory.get("regulatory_references"))
        rendered = []
        for item in refs:
            if isinstance(item, dict):
                typology = self._text(item.get("typology"))
                reference = self._text(item.get("reference"))
                if typology or reference:
                    rendered.append(" / ".join(x for x in (typology, reference) if x))
        if rendered:
            return "Agent 4 project-level references: " + "; ".join(sorted(rendered))
        if regulatory:
            return "Agent 4 regulatory assessment available; no structured references supplied."
        return "Agent 4 regulatory assessment unavailable."

    @staticmethod
    def _dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _list(value: Any) -> List[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _text(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number:
            return None
        return min(max(number, 0.0), 1.0)

    @staticmethod
    def _clamp(value: Any) -> float:
        number = Agent6Recommend._number(value)
        return number if number is not None else 0.0

    @staticmethod
    def _at_least(value: Optional[float], threshold: float) -> bool:
        return value is not None and value >= threshold

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        result = []
        for value in values:
            if value not in result:
                result.append(value)
        return result
