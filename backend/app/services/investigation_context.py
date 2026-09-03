"""
Shared Investigation Context
─────────────────────────────
Single object all agents read from and write to.
Persisted in MongoDB per case. Passed between agents by the Adaptive Planner.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class InvestigationContext:
    """
    Mutable context object shared across all agents for one investigation.
    Every agent reads the current state and writes its findings back.
    """

    def __init__(self, transaction_id: str, transaction: dict):
        self.transaction_id   = transaction_id
        self.transaction      = transaction          # raw transaction data
        self.created_at       = utcnow()

        # ── Agent outputs ─────────────────────────────────────────────────────
        self.anomaly_scores: Dict[str, Any] = {}    # Agent 1
        self.evidence:        Dict[str, Any] = {}    # Agent 2
        self.watchlist_hits:  List[Dict]     = []    # Agent 2
        self.network:         Dict[str, Any] = {}    # Agent 3
        self.sub_cases:       List[Dict]     = []    # Agent 3
        self.regulatory:      Dict[str, Any] = {}    # Agent 4
        self.shap_values:     List[Dict]     = []    # Agent 1/5
        self.explanation:     str            = ""    # Agent 5
        self.str_narrative:   str            = ""    # Agent 5
        self.recommendation:  Dict[str, Any] = {}    # Agent 6

        # ── Confidence scores per agent ───────────────────────────────────────
        self.confidence_scores: Dict[str, float] = {}

        # ── Planner trace (which agents ran, in what order, why) ──────────────
        self.agent_log: List[Dict] = []

        # ── Flags ─────────────────────────────────────────────────────────────
        self.disagreement_flag: bool = False   # XGB vs IF disagree
        self.watchlist_hit:     bool = False   # counterparty on watchlist
        self.high_risk_network: bool = False   # behavioral network risk is high

    # ── Agent write helpers ───────────────────────────────────────────────────

    def set_anomaly(self, xgb_score: float, iso_score: float,
                    probability: float, shap_values: List[Dict],
                    disagreement: bool):
        self.anomaly_scores = {
            "xgb_score":   round(xgb_score, 4),
            "iso_score":   round(iso_score, 4),
            "probability": round(probability, 4),
            "risk_level":  self._risk_level(probability),
        }
        self.shap_values       = shap_values
        self.disagreement_flag = disagreement
        self.confidence_scores["agent1_anomaly"] = round(probability, 4)
        self._log("Agent1_Anomaly", f"XGB={xgb_score:.3f} IF={iso_score:.3f} "
                  f"prob={probability:.3f} disagree={disagreement}")

    def set_evidence(self, evidence: dict, watchlist_hits: List[Dict]):
        self.evidence       = evidence
        self.watchlist_hits = watchlist_hits
        self.watchlist_hit  = len(watchlist_hits) > 0
        conf = evidence.get("evidence_confidence", 0.5)
        self.confidence_scores["agent2_evidence"] = conf
        self._log("Agent2_Evidence",
                  f"patterns={list(evidence.get('patterns', []))} "
                  f"watchlist_hits={len(watchlist_hits)}")

    def set_network(self, network: dict, sub_cases: List[Dict]):
        self.network   = network
        self.sub_cases = sub_cases

        # Agent 3 produces a behavioral, label-independent network-risk score.
        # Network size alone must not classify a network as high risk.
        network_evidence = network.get("evidence", {}) or {}

        try:
            network_risk = float(
                network_evidence.get(
                    "provisional_network_risk_score", 0.0
                ) or 0.0
            )
        except (TypeError, ValueError):
            network_risk = 0.0

        # Conservative threshold for downstream regulatory handling.
        # This keeps high_risk_network compatible with existing consumers
        # while basing it on Agent 3 behavioral evidence rather than node count.
        self.high_risk_network = network_risk >= 0.65

        # Preserve the existing Agent 3 confidence behavior for compatibility.
        try:
            node_count = float(network.get("node_count", 0) or 0)
        except (TypeError, ValueError):
            node_count = 0.0

        conf = min(node_count / 20, 1.0)
        self.confidence_scores["agent3_network"] = round(conf, 4)

        self._log(
            "Agent3_Network",
            f"nodes={network.get('node_count', 0)} "
            f"sub_cases={len(sub_cases)} "
            f"network_risk={network_risk:.3f}"
        )

    def set_regulatory(self, regulatory: dict):
        self.regulatory = regulatory
        conf = regulatory.get("regulatory_confidence", 0.5)
        self.confidence_scores["agent4_regulatory"] = conf
        self._log("Agent4_Regulatory",
                  f"typologies={regulatory.get('fatf_typologies', [])} "
                  f"pmla={regulatory.get('pmla_sections', [])}")

    def set_explanation(self, explanation: str, str_narrative: str):
        self.explanation   = explanation
        self.str_narrative = str_narrative
        self.confidence_scores["agent5_explanation"] = 0.9
        self._log(
            "Agent5_Explanation",
            f"STR narrative generated ({len(str_narrative)} chars)"
        )

    def set_recommendation(self, action: str, confidence: float,
                           reasoning: str, regulatory_basis: str):
        self.recommendation = {
            "action":           action,
            "confidence":       round(confidence, 4),
            "confidence_pct":   round(confidence * 100, 1),
            "reasoning":        reasoning,
            "regulatory_basis": regulatory_basis,
            "timestamp":        utcnow(),
        }
        self.confidence_scores["agent6_recommendation"] = round(confidence, 4)
        self._log(
            "Agent6_Recommend",
            f"action={action} confidence={confidence:.3f}"
        )

    # ── Read helpers ──────────────────────────────────────────────────────────

    @property
    def fraud_probability(self) -> float:
        return self.anomaly_scores.get("probability", 0.0)

    @property
    def risk_level(self) -> str:
        return self.anomaly_scores.get("risk_level", "low")

    @property
    def is_high_risk(self) -> bool:
        return self.fraud_probability >= 0.5 or self.watchlist_hit

    @property
    def needs_network_investigation(self) -> bool:
        return self.fraud_probability >= 0.4 or self.watchlist_hit

    @property
    def agents_completed(self) -> List[str]:
        return [entry["agent"] for entry in self.agent_log]

    # ── Serialise to dict (for MongoDB storage) ───────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id":    self.transaction_id,
            "transaction":       self.transaction,
            "created_at":        self.created_at,
            "anomaly_scores":    self.anomaly_scores,
            "evidence":          self.evidence,
            "watchlist_hits":    self.watchlist_hits,
            "network":           self.network,
            "sub_cases":         self.sub_cases,
            "regulatory":        self.regulatory,
            "shap_values":       self.shap_values,
            "explanation":       self.explanation,
            "str_narrative":     self.str_narrative,
            "recommendation":    self.recommendation,
            "confidence_scores": self.confidence_scores,
            "agent_log":         self.agent_log,
            "flags": {
                "disagreement_flag": self.disagreement_flag,
                "watchlist_hit":     self.watchlist_hit,
                "high_risk_network": self.high_risk_network,
            },
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _log(self, agent: str, detail: str):
        self.agent_log.append({
            "agent":     agent,
            "detail":    detail,
            "timestamp": utcnow(),
        })

    @staticmethod
    def _risk_level(prob: float) -> str:
        if prob >= 0.85:
            return "critical"
        if prob >= 0.65:
            return "high"
        if prob >= 0.40:
            return "medium"
        return "low"