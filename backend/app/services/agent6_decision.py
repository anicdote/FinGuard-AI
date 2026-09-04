"""Agent 6 — deterministic operational decision and case-management synthesis.

Agent 6 is the final decision layer. It consumes InvestigationContext produced by
Agents 1–5; it does not perform investigation, ML inference, regulatory analysis,
or transaction-history queries of its own.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.services.investigation_context import InvestigationContext


# Operational application thresholds. These are not legal determinations.
MEDIUM_FRAUD_THRESHOLD = 0.40
HIGH_FRAUD_THRESHOLD = 0.65
CRITICAL_FRAUD_THRESHOLD = 0.85
STRONG_EVIDENCE_THRESHOLD = 0.65
HIGH_NETWORK_RISK_THRESHOLD = 0.65


class Agent6Recommend:
    """Turn available upstream findings into a deterministic operational decision."""

    # The score is a transparent decision-support signal, not a fraud score.
    # Missing dimensions are excluded and the remaining weights are renormalised.
    WEIGHTS = {
        "fraud_probability": 0.30,
        "evidence_confidence": 0.20,
        "network_risk": 0.15,
        "regulatory_risk": 0.20,
        "watchlist": 0.10,
        "str_review": 0.05,
    }

    def run(self, ctx: InvestigationContext) -> InvestigationContext:
        anomaly = self._dict(ctx.anomaly_scores)
        evidence = self._dict(ctx.evidence)
        network = self._dict(ctx.network)
        regulatory = self._dict(ctx.regulatory)

        fraud = self._number(anomaly.get("probability"))
        evidence_confidence = self._number(evidence.get("evidence_confidence"))

        network_evidence = self._dict(network.get("evidence"))
        network_risk = self._number(
            network_evidence.get("provisional_network_risk_score")
        )

        regulatory_risk = self._number(regulatory.get("risk_score"))
        watchlist_hit = bool(ctx.watchlist_hit or ctx.watchlist_hits)
        disagreement = bool(ctx.disagreement_flag)
        patterns = self._list(evidence.get("patterns"))
        shap_values = self._list(ctx.shap_values)

        reportability = self._dict(regulatory.get("reportability_assessment"))
        str_assessment = self._dict(regulatory.get("str_assessment"))
        reportability_status = self._text(reportability.get("status"))
        str_recommendation = self._text(
            str_assessment.get("recommendation")
            or reportability.get("recommendation")
        )

        # Legacy Agent 4 fields remain supported, but are interpreted as an
        # upstream recommendation rather than as proof that an STR was filed.
        str_review = (
            reportability_status == "STR_REVIEW_RECOMMENDED"
            or str_recommendation == "REVIEW_FOR_STR"
            or regulatory.get("str_required") is True
        )

        missing = self._missing_information(
            ctx,
            evidence_confidence=evidence_confidence,
            fraud=fraud,
            network=network,
            regulatory=regulatory,
            shap_values=shap_values,
        )

        action, category = self._decide(
            fraud=fraud,
            evidence=evidence_confidence,
            network=network_risk,
            regulatory=regulatory_risk,
            watchlist_hit=watchlist_hit,
            disagreement=disagreement,
            reportability_status=reportability_status,
            str_review=str_review,
            missing=missing,
        )

        priority = self._priority(
            fraud=fraud,
            evidence=evidence_confidence,
            network=network_risk,
            regulatory=regulatory_risk,
            watchlist_hit=watchlist_hit,
            disagreement=disagreement,
            reportability_status=reportability_status,
            missing=missing,
        )

        operational_score = self._weighted_score(
            fraud_probability=fraud,
            evidence_confidence=evidence_confidence,
            network_risk=network_risk,
            regulatory_risk=regulatory_risk,
            watchlist=watchlist_hit,
            str_review=str_review,
        )

        confidence = self._confidence(
            fraud=fraud,
            evidence=evidence_confidence,
            network=network_risk,
            regulatory=regulatory_risk,
            disagreement=disagreement,
            missing=missing,
            str_review=str_review,
        )

        factors = self._decision_factors(
            fraud=fraud,
            evidence=evidence_confidence,
            network=network_risk,
            regulatory=regulatory_risk,
            watchlist_hit=watchlist_hit,
            disagreement=disagreement,
            reportability_status=reportability_status,
            str_recommendation=str_recommendation,
            patterns=patterns,
            missing=missing,
        )

        requires_human_review = (
            action != "CLOSE"
            or bool(missing)
            or disagreement
            or str_review
            or reportability_status == "FURTHER_REVIEW_REQUIRED"
        )

        reasoning = self._reasoning(
            action=action,
            priority=priority,
            category=category,
            factors=factors,
            missing=missing,
            has_agent5_explanation=bool(self._text(ctx.explanation)),
            has_agent5_str_draft=bool(self._text(ctx.str_narrative)),
        )

        # Preserve the existing API contract and add only additive decision data.
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
            "network_risk_score": network_risk,
            "decision_factors": factors,
            "supporting_evidence": self._supporting_evidence(ctx),
            "regulatory_assessment": self._regulatory_snapshot(regulatory),
            "str_assessment": self._str_assessment_snapshot(regulatory),
            "str_status": self._str_status(
                reportability_status,
                str_recommendation,
                str_review,
            ),
            "str_filing_status": "not_filed",
            "agent5_explanation": self._text(ctx.explanation),
            "agent5_str_draft": self._text(ctx.str_narrative),
            "missing_information": missing,
            "requires_human_review": requires_human_review,
            "case_action": self._case_action(action),
            "decision_basis": "deterministic_evidence_aware_synthesis",
        })
        return ctx

    def _decide(
        self,
        *,
        fraud: Optional[float],
        evidence: Optional[float],
        network: Optional[float],
        regulatory: Optional[float],
        watchlist_hit: bool,
        disagreement: bool,
        reportability_status: str,
        str_review: bool,
        missing: List[str],
    ) -> Tuple[str, str]:
        # Agent 4 owns regulatory interpretation. Agent 6 routes that
        # recommendation; it never invents an STR conclusion.
        if str_review and (
            reportability_status == "STR_REVIEW_RECOMMENDED"
            or self._text(reportability_status) == ""
        ) and (evidence is None or evidence >= STRONG_EVIDENCE_THRESHOLD):
            return "FILE_STR", "STR_REVIEW"

        if reportability_status == "FURTHER_REVIEW_REQUIRED":
            if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
                return "BLOCK", "HIGH_RISK_REVIEW"
            return "REQUEST_INFO", "FURTHER_REVIEW"

        if reportability_status == "NOT_ENOUGH_EVIDENCE" and str_review is False:
            if self._at_least(fraud, .85) and evidence is not None and evidence < .65:
                return "REQUEST_INFO", "EVIDENCE_LIMITED_REVIEW"

        # A watchlist/PEP match is high-value context, not proof by itself.
        if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
            return "BLOCK", "HIGH_RISK_REVIEW"

        # High fraud probability never means "fraud confirmed". If evidence is
        # unavailable or weak, request information instead of escalating as fact.
        if self._at_least(fraud, CRITICAL_FRAUD_THRESHOLD):
            if evidence is None or evidence < STRONG_EVIDENCE_THRESHOLD:
                return "REQUEST_INFO", "EVIDENCE_LIMITED_REVIEW"
            return "ESCALATE", "HIGH_RISK_REVIEW"

        if self._at_least(network, HIGH_NETWORK_RISK_THRESHOLD):
            if evidence is None or evidence < STRONG_EVIDENCE_THRESHOLD:
                return "REQUEST_INFO", "NETWORK_REVIEW_WITH_LIMITED_EVIDENCE"
            return "ESCALATE", "NETWORK_RISK_REVIEW"

        if disagreement and self._at_least(fraud, MEDIUM_FRAUD_THRESHOLD):
            return "ESCALATE", "MODEL_DISAGREEMENT_REVIEW"

        if self._at_least(fraud, HIGH_FRAUD_THRESHOLD) and evidence is not None and evidence < STRONG_EVIDENCE_THRESHOLD:
            return "REQUEST_INFO", "EVIDENCE_LIMITED_REVIEW"

        if (
            self._at_least(fraud, .50)
            or self._at_least(network, .40)
            or self._at_least(regulatory, .55)
        ):
            return "ESCALATE", "MULTI_SIGNAL_REVIEW"

        if self._at_least(fraud, .35):
            return "MONITOR", "MONITORING"

        if (
            (evidence is not None and evidence < .50)
            or str_review
        ):
            return "REQUEST_INFO", "INFORMATION_REVIEW"

        return "CLOSE", "NO_ACTION"

    def _priority(
        self,
        *,
        fraud: Optional[float],
        evidence: Optional[float],
        network: Optional[float],
        regulatory: Optional[float],
        watchlist_hit: bool,
        disagreement: bool,
        reportability_status: str,
        missing: List[str],
    ) -> str:
        if reportability_status == "STR_REVIEW_RECOMMENDED":
            return "critical"
        if watchlist_hit and self._at_least(fraud, .50) and self._at_least(evidence, .65):
            return "critical"
        if disagreement or self._at_least(network, .65):
            return "high"
        if self._at_least(fraud, .65) or self._at_least(regulatory, .55):
            return "high"
        if self._at_least(fraud, .35) or (evidence is not None and evidence < .50):
            return "medium"
        if missing:
            return "medium"
        return "low"

    def _weighted_score(self, **values: Any) -> float:
        available = []
        for name, weight in self.WEIGHTS.items():
            value = values.get(name)
            if value is None:
                continue
            numeric = float(bool(value)) if name in {"watchlist", "str_review"} else self._number(value)
            if numeric is not None:
                available.append((numeric, weight))
        if not available:
            return 0.0
        total_weight = sum(weight for _, weight in available)
        return round(sum(value * weight for value, weight in available) / total_weight, 4)

    def _confidence(
        self,
        *,
        fraud: Optional[float],
        evidence: Optional[float],
        network: Optional[float],
        regulatory: Optional[float],
        disagreement: bool,
        missing: List[str],
        str_review: bool,
    ) -> float:
        score = self._weighted_score(
            fraud_probability=fraud,
            evidence_confidence=evidence,
            network_risk=network,
            regulatory_risk=regulatory,
            str_review=str_review,
        )
        if disagreement:
            score *= .85
        score -= min(.20, .03 * len(missing))
        if str_review and evidence is not None and evidence < STRONG_EVIDENCE_THRESHOLD:
            score *= .75
        return round(max(.20, min(score, .99)), 4)

    def _decision_factors(
        self,
        *,
        fraud: Optional[float],
        evidence: Optional[float],
        network: Optional[float],
        regulatory: Optional[float],
        watchlist_hit: bool,
        disagreement: bool,
        reportability_status: str,
        str_recommendation: str,
        patterns: List[Any],
        missing: List[str],
    ) -> List[str]:
        factors: List[str] = []
        if fraud is not None:
            factors.append(f"Agent 1 fraud probability={fraud:.3f}.")
        if evidence is not None:
            factors.append(f"Agent 2 evidence confidence={evidence:.3f}.")
        if patterns:
            factors.append(
                "Agent 2 observed patterns: "
                + ", ".join(sorted(str(item) for item in patterns))
                + "."
            )
        if network is not None:
            factors.append(
                f"Agent 3 provisional network risk={network:.3f}; network size is contextual, not the primary risk signal."
            )
        if regulatory is not None:
            factors.append(f"Agent 4 regulatory risk score={regulatory:.3f}.")
        if watchlist_hit:
            factors.append("Agent 2 reports one or more watchlist/PEP hits.")
        if disagreement:
            factors.append("Agent 1 reports model disagreement.")
        if reportability_status:
            factors.append(f"Agent 4 reportability assessment={reportability_status}.")
        if str_recommendation:
            factors.append(f"Agent 4 STR assessment={str_recommendation}.")
        if missing:
            factors.append(f"Investigation information gaps={len(missing)}.")
        return factors

    def _reasoning(
        self,
        *,
        action: str,
        priority: str,
        category: str,
        factors: List[str],
        missing: List[str],
        has_agent5_explanation: bool,
        has_agent5_str_draft: bool,
    ) -> str:
        parts = [f"{action}: priority={priority}; category={category}."] + factors
        if missing:
            parts.append("Missing information limits decision confidence.")
        if has_agent5_explanation:
            parts.append("Agent 5 explanation is preserved for investigator review.")
        if has_agent5_str_draft:
            parts.append(
                "Agent 5 STR output is treated as a draft/recommendation only; it does not indicate that an STR has been filed."
            )
        return " ".join(parts)

    def _missing_information(
        self,
        ctx: InvestigationContext,
        *,
        evidence_confidence: Optional[float],
        fraud: Optional[float],
        network: Dict[str, Any],
        regulatory: Dict[str, Any],
        shap_values: List[Any],
    ) -> List[str]:
        result: List[str] = []
        for item in self._list(regulatory.get("missing_information")):
            text = self._text(item)
            if text and text not in result:
                result.append(text)

        if fraud is None:
            result.append("Agent 1 fraud probability is unavailable because anomaly output is missing or malformed.")
        if not ctx.evidence:
            result.append("Agent 2 evidence is unavailable because evidence output is missing.")
        elif evidence_confidence is None:
            result.append("Agent 2 evidence confidence is unavailable or malformed.")
        if not network:
            result.append("Agent 3 network investigation is unavailable because network output is missing.")
        if not regulatory:
            result.append("Agent 4 regulatory assessment is unavailable because regulatory output is missing.")
        if not ctx.explanation:
            result.append("Agent 5 explanation is unavailable because explanation output is missing.")
        if not ctx.str_narrative:
            result.append("Agent 5 STR draft/narrative is unavailable.")
        if not shap_values:
            result.append("Agent 1 SHAP driver information is unavailable.")

        txn = ctx.transaction if isinstance(ctx.transaction, dict) else {}
        if not txn.get("customer_id") and not txn.get("customerId"):
            result.append("Customer identification information is unavailable in the current investigation context.")
        if not txn.get("account_id") and not txn.get("accountId"):
            result.append("Account identification information is unavailable in the current investigation context.")
        if not txn.get("counterparty") and not txn.get("nameDest") and not txn.get("counterpartyAccount"):
            result.append("Counterparty information is unavailable in the current investigation context.")
        if not txn.get("timestamp"):
            result.append("Transaction timestamp is unavailable in the current investigation context.")
        return self._dedupe(result)

    def _supporting_evidence(self, ctx: InvestigationContext) -> List[Any]:
        regulatory = self._dict(ctx.regulatory)
        regulatory_evidence = self._list(regulatory.get("supporting_evidence"))
        if regulatory_evidence:
            return regulatory_evidence
        result: List[Any] = []
        if ctx.evidence:
            result.append({"source": "Agent2_Evidence", "items": ctx.evidence})
        if ctx.network:
            result.append({
                "source": "Agent3_Network",
                "items": self._dict(ctx.network.get("evidence")),
            })
        if ctx.watchlist_hits:
            result.append({"source": "Agent2_Evidence", "type": "watchlist", "items": ctx.watchlist_hits})
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
        return {key: reportability[key] for key in ("recommendation", "confidence") if key in reportability}

    @staticmethod
    def _str_status(status: str, recommendation: str, str_review: bool) -> str:
        if str_review:
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

    @staticmethod
    def _regulatory_basis(regulatory: Dict[str, Any]) -> str:
        refs = Agent6Recommend._list(regulatory.get("regulatory_references"))
        rendered = []
        for item in refs:
            if isinstance(item, dict):
                typology = Agent6Recommend._text(item.get("typology"))
                reference = Agent6Recommend._text(item.get("reference"))
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
    def _at_least(value: Optional[float], threshold: float) -> bool:
        return value is not None and value >= threshold

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        result: List[str] = []
        for value in values:
            # Regulatory and context checks can express the same missing fact
            # with minor wording differences.  Keep the first (usually more
            # specific) statement while preserving genuinely distinct facts.
            normalized = " ".join(value.lower().replace("not available", "unavailable").split())
            if not any(
                normalized == " ".join(existing.lower().replace("not available", "unavailable").split())
                or (
                    "customer identification information" in normalized
                    and "customer identification information" in existing.lower()
                )
                for existing in result
            ):
                result.append(value)
        return result
