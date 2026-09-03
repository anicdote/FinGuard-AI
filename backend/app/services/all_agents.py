"""
FinGuard AI — All 6 Agents
────────────────────────────
All agents in one file for simplicity.
Import: from app.services.all_agents import Agent1Anomaly, Agent2Evidence, etc.
"""

import logging
import random
from datetime import datetime, timezone
from typing import Dict, List, Any

from app.services.investigation_context import InvestigationContext
from app.services.fraud_prediction import fraud_service

logger = logging.getLogger(__name__)


# ══ AGENT 1 — Anomaly Detection ═══════════════════════════════════════════════

class Agent1Anomaly:
    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(f"[Agent1] Anomaly detection for {ctx.transaction_id}")
        result = fraud_service.score_transaction(ctx.transaction)
        ctx.set_anomaly(
            xgb_score    = result["xgb_score"],
            iso_score    = result["iso_score"],
            probability  = result["fraud_probability"],
            shap_values  = result["shap_values"],
            disagreement = result["disagreement_flag"],
        )
        if result["disagreement_flag"]:
            logger.warning(f"[Agent1] Model disagreement — XGB={result['xgb_score']:.3f} "
                           f"IF={result['iso_score']:.3f} — novel pattern possible")
        return ctx


# ══ AGENT 2 — Evidence Gathering ══════════════════════════════════════════════

WATCHLIST = {
    "Indo-Gulf Trading Co", "Dubai Shell Corp", "Panama Holdings Ltd",
    "Hong Kong Layering LLC", "Cayman Islands Trust", "Crypto Gateway Ltd",
    "Singapore Offshore Co", "Al-Rashid Exchange", "Global Money Transfer",
    "FastCash Services", "QuickRemit Inc", "NovaPay Networks",
    "ACC-9999", "ACC-8888", "ACC-7777",
}

PEP_LIST = {
    "Rajesh Kumar Sharma", "Mohammad Al-Farsi", "Zhang Wei Holdings",
    "Viktor Petrov LLC", "Carlos Mendez Trading",
}

NIGHT_HOURS   = set(range(0, 6)) | {23}
CTR_THRESHOLD = 1_000_000  # ₹10L


class Agent2Evidence:
    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(f"[Agent2] Evidence gathering for {ctx.transaction_id}")
        txn          = ctx.transaction
        amount       = float(txn.get("amount", 0))
        hour         = int(txn.get("hour", 12))
        channel      = txn.get("channel", "")
        location     = txn.get("location", "")
        counterparty = txn.get("counterparty", txn.get("nameDest", ""))
        old_bal      = float(txn.get("oldbalanceOrg", txn.get("oldbalanceOrig", 0)))
        new_bal      = float(txn.get("newbalanceOrig", old_bal))

        patterns   = []
        risk_boost = 0.0

        if 0.85 * CTR_THRESHOLD <= amount < CTR_THRESHOLD:
            patterns.append("structuring_near_ctr");  risk_boost += 0.25
        if amount > 10_000 and amount % 10_000 == 0:
            patterns.append("round_amount");          risk_boost += 0.10
        if hour in NIGHT_HOURS:
            patterns.append("night_hour_transaction"); risk_boost += 0.10
        if channel in {"Wire Transfer", "Crypto"}:
            patterns.append("high_risk_channel");     risk_boost += 0.15
        if amount > CTR_THRESHOLD:
            patterns.append("above_ctr_threshold");   risk_boost += 0.20
        if old_bal > 0 and new_bal == 0:
            patterns.append("complete_balance_drain"); risk_boost += 0.20

        watchlist_hits       = self._check_watchlist(counterparty, location)
        if watchlist_hits:    risk_boost += 0.35

        evidence_confidence  = min(0.4 + risk_boost, 0.95)
        evidence = {
            "patterns":            patterns,
            "risk_boost":          round(risk_boost, 3),
            "evidence_confidence": round(evidence_confidence, 3),
            "amount":              amount,
            "hour":                hour,
            "channel":             channel,
            "location":            location,
            "counterparty":        counterparty,
            "old_balance":         old_bal,
            "new_balance":         new_bal,
            "pattern_count":       len(patterns),
        }
        ctx.set_evidence(evidence, watchlist_hits)
        logger.info(f"[Agent2] patterns={patterns} watchlist={len(watchlist_hits)}")
        return ctx

    def _check_watchlist(self, counterparty: str, location: str) -> List[Dict]:
        hits    = []
        cp      = (counterparty or "").strip().lower()
        for entity in WATCHLIST:
            if entity.lower() in cp:
                hits.append({"list": "OFAC/Internal", "entity": entity,
                              "match": counterparty, "type": "counterparty"})
        for pep in PEP_LIST:
            if pep.lower() in cp:
                hits.append({"list": "PEP", "entity": pep,
                              "match": counterparty, "type": "pep"})
        return hits


# ══ AGENT 3 — Network Investigation ═══════════════════════════════════════════

MAX_SUBCASES          = 5
SUBCASES_THRESHOLD    = 0.70


class Agent3Network:
    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(f"[Agent3] Network investigation for {ctx.transaction_id}")
        txn = ctx.transaction

        nodes, edges = self._build_graph(txn, ctx.fraud_probability)

        sub_cases = []
        primary_id = txn.get("accountId", txn.get("id", ""))
        for node in nodes:
            if node["account_id"] == primary_id:
                continue
            if node["risk_score"] >= SUBCASES_THRESHOLD and \
               len(sub_cases) < MAX_SUBCASES:
                sub_cases.append({
                    "account_id":   node["account_id"],
                    "risk_score":   node["risk_score"],
                    "risk_level":   node["risk_level"],
                    "reason":       f"Connected account — risk {node['risk_score']:.2f}",
                    "auto_created": True,
                })

        scc = self._find_clusters(nodes, edges)
        network = {
            "node_count":   len(nodes),
            "edge_count":   len(edges),
            "nodes":        nodes,
            "edges":        edges,
            "scc_clusters": scc,
            "max_pagerank": max((n["pagerank"] for n in nodes), default=0),
            "central_node": max(nodes, key=lambda n: n["pagerank"],
                                default={}).get("account_id", ""),
        }
        ctx.set_network(network, sub_cases)
        logger.info(f"[Agent3] nodes={len(nodes)} sub_cases={len(sub_cases)}")
        return ctx

    def _build_graph(self, txn: dict, base_risk: float):
        primary_id   = txn.get("accountId", txn.get("id", "ACC-PRIMARY"))
        counterparty = txn.get("counterparty", txn.get("nameDest", "ACC-DEST"))
        channel      = txn.get("channel", "NEFT")
        amount       = float(txn.get("amount", 0))

        nodes = [
            self._node(primary_id,   base_risk,        True),
            self._node(counterparty, base_risk * 0.85),
        ]
        edges = [{"from": primary_id, "to": counterparty,
                  "amount": amount, "channel": channel}]

        if base_risk >= 0.5:
            for i in range(random.randint(2, 6)):
                acc  = f"ACC-{random.randint(1000,9999)}"
                risk = round(base_risk * random.uniform(0.5, 0.95), 3)
                nodes.append(self._node(acc, risk))
                edges.append({"from": counterparty, "to": acc,
                              "amount": round(amount * random.uniform(0.1, 0.5)),
                              "channel": random.choice(["UPI","NEFT","IMPS"])})

        pr = {n["account_id"]: 1.0 / len(nodes) for n in nodes}
        for _ in range(5):
            new_pr = {}
            for node in nodes:
                acc = node["account_id"]
                in_e = [e for e in edges if e["to"] == acc]
                new_pr[acc] = 0.15 / len(nodes) + 0.85 * sum(
                    pr.get(e["from"], 0) /
                    max(sum(1 for ee in edges if ee["from"] == e["from"]), 1)
                    for e in in_e)
            pr = new_pr
        for node in nodes:
            node["pagerank"] = round(pr.get(node["account_id"], 0), 4)
        return nodes, edges

    def _node(self, acc_id: str, risk: float, primary=False) -> dict:
        risk  = round(min(max(risk, 0.0), 1.0), 3)
        level = ("critical" if risk >= 0.85 else "high" if risk >= 0.65
                 else "medium" if risk >= 0.40 else "low")
        return {"account_id": acc_id, "risk_score": risk,
                "risk_level": level, "is_primary": primary, "pagerank": 0.0}

    def _find_clusters(self, nodes, edges) -> List[Dict]:
        if not nodes: return []
        return [{"cluster_id": "SCC-1", "node_count": len(nodes),
                 "account_ids": [n["account_id"] for n in nodes],
                 "avg_risk": round(sum(n["risk_score"] for n in nodes)/len(nodes), 3)}]


# ══ AGENT 4 — Regulatory Risk ═════════════════════════════════════════════════

# ══ AGENT 4 — Regulatory Risk ═══════════════════════════════════════════════

# These are project-level regulatory reference mappings.
# They are used to support an investigation and are NOT a final legal
# determination. Do not treat these mappings as legal advice.

FATF_TYPOLOGIES = {
    "T1_Structuring": {
        "name": "Structuring / Smurfing",
        "description": (
            "Breaking large amounts into smaller transactions to avoid "
            "reporting thresholds"
        ),
        "pmla_section": "Section 3 & Section 12(1)(a)",
        "indicators": [
            "structuring_near_ctr",
            "round_amount",
            "multiple_transactions",
        ],
        "severity": 0.85,
    },
    "T2_TBML": {
        "name": "Trade-Based Money Laundering",
        "description": (
            "Using international trade transactions to move illicit funds"
        ),
        "pmla_section": "Section 3",
        "indicators": [
            "high_risk_channel",
            "international_transfer",
        ],
        "severity": 0.80,
    },
    "T3_Layering": {
        "name": "Layering",
        "description": (
            "Complex series of transactions to disguise origin of funds"
        ),
        "pmla_section": "Section 3 & Section 4",
        "indicators": [
            "complete_balance_drain",
            "high_risk_channel",
            "above_ctr_threshold",
        ],
        "severity": 0.90,
    },
    "T4_CyberFraud": {
        "name": "Cyber-Enabled Fraud",
        "description": (
            "Account takeover, SIM-swap, or digital fraud patterns"
        ),
        "pmla_section": "Section 3",
        "indicators": [
            "night_hour_transaction",
            "high_risk_channel",
            "complete_balance_drain",
        ],
        "severity": 0.75,
    },
    "T5_CashIntensive": {
        "name": "Cash-Intensive Business",
        "description": (
            "Unusually high cash transactions inconsistent with account profile"
        ),
        "pmla_section": "Section 12(1)(a)",
        "indicators": [
            "above_ctr_threshold",
            "round_amount",
        ],
        "severity": 0.70,
    },
}

# Agent 4 project-level assessment thresholds.
# These are transparent demo thresholds, not legal/regulatory determinations.
AGENT4_NETWORK_SIGNAL_NODES = 2
AGENT4_STRONG_NETWORK_NODES = 5
AGENT4_STRONG_EVIDENCE_THRESHOLD = 0.65

AGENT4_RISK_CRITICAL_THRESHOLD = 0.75
AGENT4_RISK_HIGH_THRESHOLD = 0.55
AGENT4_RISK_MEDIUM_THRESHOLD = 0.30

AGENT4_TYPOLOGY_CONFIDENCE_BASE = 0.30
AGENT4_TYPOLOGY_CONFIDENCE_SCALE = 0.65
AGENT4_MAX_TYPOLOGY_CONFIDENCE = 0.95

class Agent4Regulatory:

    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(
            f"[Agent4] Regulatory assessment for {ctx.transaction_id}"
        )

        patterns = list(ctx.evidence.get("patterns", []))
        fraud_probability = self._clamp(ctx.fraud_probability)
        evidence_confidence = self._clamp(
            ctx.evidence.get("evidence_confidence", 0.0)
        )

        # Agent 3 is still under development.
        # Therefore Agent 4 must safely handle missing or partial network data.
        network = ctx.network if isinstance(ctx.network, dict) else {}
        node_count = self._safe_int(network.get("node_count", 0))
        sub_case_count = len(ctx.sub_cases or [])

        has_network_signal = node_count > AGENT4_NETWORK_SIGNAL_NODES
        has_strong_network_signal = node_count > AGENT4_STRONG_NETWORK_NODES

        watchlist_hit = bool(ctx.watchlist_hit or ctx.watchlist_hits)

        # ---------------------------------------------------------------
        # 1. Match regulatory typologies using ONLY available evidence.
        # ---------------------------------------------------------------

        matched = []
        pmla_sections = set()

        for code, typology in FATF_TYPOLOGIES.items():

            indicator_hits = [
                indicator
                for indicator in typology["indicators"]
                if indicator in patterns
            ]

            # Network information can support Layering, but does not create
            # a typology match by itself unless other evidence exists.
            if (
                code == "T3_Layering"
                and has_network_signal
                and indicator_hits
            ):
                indicator_hits.append("network_risk")

            # A watchlist hit is regulatory context, but it should not
            # manufacture a typology match on its own.
            if watchlist_hit and indicator_hits:
                indicator_hits.append("watchlist_hit")

            if not indicator_hits:
                continue

            base_confidence = len(
                set(indicator_hits)
                & set(typology["indicators"])
            ) / len(typology["indicators"])

            # Keep confidence evidence-driven and bounded.
            confidence = min(
    AGENT4_MAX_TYPOLOGY_CONFIDENCE,
    AGENT4_TYPOLOGY_CONFIDENCE_BASE
    + (base_confidence * AGENT4_TYPOLOGY_CONFIDENCE_SCALE),
)

            matched.append(
                {
                    "code": code,
                    "name": typology["name"],
                    "description": typology["description"],
                    "confidence": round(confidence, 3),
                    "severity": typology["severity"],
                    "pmla": typology["pmla_section"],
                    "matched_indicators": list(
                        dict.fromkeys(indicator_hits)
                    ),
                }
            )

            pmla_sections.add(typology["pmla_section"])

        matched.sort(
            key=lambda item: (
                item["confidence"],
                item["severity"],
            ),
            reverse=True,
        )

        # ---------------------------------------------------------------
        # 2. Build evidence-backed regulatory signals.
        # ---------------------------------------------------------------

        supporting_evidence = []

        if patterns:
            supporting_evidence.append(
                {
                    "source": "Agent2_Evidence",
                    "type": "transaction_patterns",
                    "items": patterns,
                }
            )

        if watchlist_hit:
            supporting_evidence.append(
                {
                    "source": "Agent2_Evidence",
                    "type": "watchlist",
                    "items": ctx.watchlist_hits,
                }
            )

        if has_network_signal:
            supporting_evidence.append(
                {
                    "source": "Agent3_Network",
                    "type": "network",
                    "items": {
                        "node_count": node_count,
                        "sub_case_count": sub_case_count,
                        "high_risk_network": has_strong_network_signal,
                    },
                }
            )

        # Fraud probability is explicitly retained as an anomaly signal,
        # but is NOT treated as regulatory evidence by itself.
        if fraud_probability > 0:
            supporting_evidence.append(
                {
                    "source": "Agent1_Anomaly",
                    "type": "anomaly_signal",
                    "items": {
                        "fraud_probability": round(
                            fraud_probability,
                            4,
                        ),
                        "risk_level": ctx.risk_level,
                    },
                }
            )

        # ---------------------------------------------------------------
        # 3. Determine overall regulatory risk.
        #
        # This is an explainable project-level assessment, not a legal
        # determination. Each available dimension contributes independently.
        # ---------------------------------------------------------------

        risk_components = []

        if evidence_confidence > 0:
            risk_components.append(evidence_confidence)

        if matched:
            risk_components.append(
                max(item["confidence"] for item in matched)
            )

        if watchlist_hit:
            risk_components.append(1.0)

        if has_network_signal:
            network_signal = min(node_count / 10.0, 1.0)
            risk_components.append(network_signal)

        # Fraud contributes to overall investigation risk, but never creates
        # an STR recommendation by itself.
        risk_components.append(fraud_probability)

        risk_score = (
            sum(risk_components) / len(risk_components)
            if risk_components
            else 0.0
        )

        if risk_score >= AGENT4_RISK_CRITICAL_THRESHOLD:
            overall_risk = "critical"
        elif risk_score >= AGENT4_RISK_HIGH_THRESHOLD:
            overall_risk = "high"
        elif risk_score >= AGENT4_RISK_MEDIUM_THRESHOLD:
            overall_risk = "medium"
        else:
            overall_risk = "low"

        # ---------------------------------------------------------------
        # 4. Assess reportability separately from fraud risk.
        #
        # A high fraud probability alone is NOT sufficient.
        # ---------------------------------------------------------------

        independent_regulatory_signals = 0

        if matched:
            independent_regulatory_signals += 1

        if watchlist_hit:
            independent_regulatory_signals += 1

        if has_strong_network_signal:
            independent_regulatory_signals += 1

        strong_evidence = (
    evidence_confidence >= AGENT4_STRONG_EVIDENCE_THRESHOLD
)

        if (
            independent_regulatory_signals >= 2
            and strong_evidence
        ):
            reportability_status = "STR_REVIEW_RECOMMENDED"
            reportability_confidence = min(
                0.95,
                0.55
                + 0.10 * independent_regulatory_signals
                + 0.20 * evidence_confidence,
            )
            str_recommendation = "REVIEW_FOR_STR"
            reportability_reason = (
                "Multiple independent regulatory indicators are supported "
                "by available investigation evidence."
            )

        elif (
            independent_regulatory_signals >= 1
            or strong_evidence
        ):
            reportability_status = "FURTHER_REVIEW_REQUIRED"
            reportability_confidence = 0.60
            str_recommendation = "FURTHER_REVIEW"
            reportability_reason = (
                "The investigation contains risk indicators, but the "
                "available evidence is not sufficient for a strong "
                "reportability conclusion."
            )

        else:
            reportability_status = "NOT_ENOUGH_EVIDENCE"
            reportability_confidence = 0.35
            str_recommendation = "NO_STR_RECOMMENDATION"
            reportability_reason = (
                "The available investigation context does not contain "
                "sufficient independent regulatory indicators."
            )

        # ---------------------------------------------------------------
        # 5. Identify information that is unavailable to Agent 4.
        # ---------------------------------------------------------------

        missing_information = []

        if not ctx.transaction.get("customer_id"):
            missing_information.append(
                "Customer identification information is not available "
                "in the investigation context."
            )

        if not ctx.transaction.get("source_of_funds"):
            missing_information.append(
                "Source-of-funds information is not available."
            )

        if not ctx.transaction.get("beneficial_owner"):
            missing_information.append(
                "Beneficial-owner information is not available."
            )

        if not ctx.transaction.get("transaction_history"):
            missing_information.append(
                "Broader transaction history is not available."
            )

        if not (
    ctx.transaction.get("counterparty")
    or ctx.transaction.get("nameDest")
):
            missing_information.append(
                "Counterparty details are limited or unavailable."
            )

        if not network:
            missing_information.append(
                "Network investigation data is not available."
            )

        # ---------------------------------------------------------------
        # 6. Build a concise, traceable rationale.
        # ---------------------------------------------------------------

        rationale_parts = []

        if matched:
            rationale_parts.append(
                "Matched typologies: "
                + ", ".join(item["code"] for item in matched)
                + "."
            )

        if patterns:
            rationale_parts.append(
                "Observed transaction patterns: "
                + ", ".join(patterns)
                + "."
            )

        if watchlist_hit:
            rationale_parts.append(
                f"Watchlist/PEP matches detected: "
                f"{len(ctx.watchlist_hits)}."
            )

        if has_network_signal:
            rationale_parts.append(
                f"Network investigation contains {node_count} nodes "
                f"and {sub_case_count} sub-case(s)."
            )

        rationale_parts.append(reportability_reason)

        # ---------------------------------------------------------------
        # 7. Preserve legacy fields consumed by Agents 5/6/frontend.
        # ---------------------------------------------------------------

        regulatory_confidence = (
            sum(item["confidence"] for item in matched) / len(matched)
            if matched
            else (
                evidence_confidence
                if evidence_confidence > 0
                else 0.30
            )
        )

        max_severity = max(
            (item["severity"] for item in matched),
            default=0.0,
        )

        # Legacy boolean fields are now derived from the structured
        # reportability assessment rather than fraud probability alone.
        str_required = (
            reportability_status == "STR_REVIEW_RECOMMENDED"
        )

        fiu_ind_reportable = str_required

        regulatory_result = {
            # Existing compatibility fields
            "fatf_typologies": matched,
            "primary_typology": matched[0] if matched else None,
            "pmla_sections": list(pmla_sections),
            "regulatory_confidence": round(
                regulatory_confidence,
                3,
            ),
            "max_severity": round(max_severity, 3),
            "fiu_ind_reportable": fiu_ind_reportable,
            "str_required": str_required,

            # New structured Agent 4 assessment
            "overall_risk": overall_risk,
            "risk_score": round(risk_score, 3),

            "regulatory_references": [
                {
                    "reference": item["pmla"],
                    "typology": item["code"],
                    "reference_type": "project_reference",
                    "legal_determination": False,
                }
                for item in matched
            ],

            "reportability_assessment": {
                "status": reportability_status,
                "confidence": round(
                    reportability_confidence,
                    3,
                ),
                "recommendation": str_recommendation,
                "rationale": reportability_reason,
            },

            "str_assessment": {
                "recommendation": str_recommendation,
                "confidence": round(
                    reportability_confidence,
                    3,
                ),
                "supporting_typologies": [
                    item["code"] for item in matched
                ],
            },

            "supporting_evidence": supporting_evidence,

            "missing_information": missing_information,

            "rationale": " ".join(rationale_parts),

            "assessment_scope": (
                "Project-level regulatory risk assessment based only "
                "on the investigation context available to Agent 4. "
                "This is not a final legal determination."
            ),
        }

        ctx.set_regulatory(regulatory_result)

        logger.info(
            f"[Agent4] typologies="
            f"{[item['code'] for item in matched]} "
            f"risk={overall_risk} "
            f"reportability={reportability_status}"
        )

        return ctx

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return round(
                min(max(float(value), 0.0), 1.0),
                4,
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

# ══ AGENT 5 — Explanation + STR ═══════════════════════════════════════════════

class Agent5Explanation:
    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(f"[Agent5] Generating explanation for {ctx.transaction_id}")
        ctx.set_explanation(
            self._build_explanation(ctx),
            self._build_str(ctx)
        )
        return ctx

    def _build_explanation(self, ctx: InvestigationContext) -> str:
        prob     = ctx.fraud_probability
        level    = ctx.risk_level
        shap     = ctx.shap_values
        typos    = ctx.regulatory.get("fatf_typologies", [])
        patterns = ctx.evidence.get("patterns", [])
        nodes    = ctx.network.get("node_count", 0)

        lines = [f"Transaction {ctx.transaction_id} flagged with "
                 f"{level.upper()} risk ({prob:.1%})."]

        if shap:
            contrib = ", ".join(
                f"{s['feature'].replace('_',' ')}: "
                f"{'↑' if s['value']>0 else '↓'}{abs(s['value']):.3f}"
                for s in shap[:3])
            lines.append(f"Key drivers: {contrib}.")

        if patterns:
            lines.append(f"Patterns: {', '.join(p.replace('_',' ') for p in patterns)}.")

        if nodes > 2:
            lines.append(f"Network: {nodes} connected accounts, "
                         f"{len(ctx.sub_cases)} sub-case(s) auto-created.")

        if ctx.watchlist_hit:
            lines.append(f"Watchlist: {', '.join(h['entity'] for h in ctx.watchlist_hits)}.")

        if typos:
            p = typos[0]
            lines.append(f"Typology: {p['name']} ({p['code']}) — "
                         f"{p['confidence']:.1%} confidence. PMLA: {p['pmla']}.")

        if ctx.disagreement_flag:
            lines.append("Note: models disagree — possible novel fraud pattern.")

        return " ".join(lines)

    def _build_str(self, ctx: InvestigationContext) -> str:
        txn    = ctx.transaction
        now    = datetime.now(timezone.utc).strftime("%d %B %Y")
        typos  = ctx.regulatory.get("fatf_typologies", [])
        pmla   = ctx.regulatory.get("pmla_sections", [])
        pt     = typos[0] if typos else {"name":"Suspicious Activity",
                                          "code":"Unknown","pmla":"Section 3"}
        return f"""SUSPICIOUS TRANSACTION REPORT (STR)
FIU-IND | Date: {now} | Ref: STR-{ctx.transaction_id}
{'─'*60}
Account:      {txn.get('accountId', txn.get('id','Unknown'))}
Amount:       ₹{float(txn.get('amount',0)):,.2f}
Channel:      {txn.get('channel','Unknown')}
Counterparty: {txn.get('counterparty', txn.get('nameDest','Unknown'))}
Risk Score:   {ctx.fraud_probability:.1%} ({ctx.risk_level.upper()})
{'─'*60}
DESCRIPTION:
{ctx.explanation}
{'─'*60}
TYPOLOGY:     {pt['name']} ({pt['code']})
PMLA 2002:    {', '.join(pmla) if pmla else 'Section 3'}
NETWORK:      {ctx.network.get('node_count',0)} accounts | {len(ctx.sub_cases)} sub-cases
WATCHLIST:    {len(ctx.watchlist_hits)} hit(s)
AGENTS RAN:   {len(ctx.agents_completed)}
{'─'*60}
ACTION:       {ctx.recommendation.get('action','Pending')}
APPROVED BY:  [Pending biometric verification]
Prepared by FinGuard AI Autonomous Investigation System""".strip()


# ══ AGENT 6 — Action Recommendation ═══════════════════════════════════════════

class Agent6Recommend:
    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(f"[Agent6] Recommendation for {ctx.transaction_id}")
        prob        = ctx.fraud_probability
        typos       = ctx.regulatory.get("fatf_typologies", [])
        has_network = ctx.network.get("node_count", 0) > 2
        str_req     = ctx.regulatory.get("str_required", False)
        patterns    = ctx.evidence.get("patterns", [])

        action     = self._action(prob, ctx.watchlist_hit, str_req,
                                  has_network, ctx.disagreement_flag)
        confidence = self._confidence(ctx)
        reasoning  = self._reasoning(action, prob, typos, patterns,
                                     has_network, ctx)
        pmla       = ctx.regulatory.get("pmla_sections", ["Section 3"])
        reg_basis  = (f"PMLA 2002 {', '.join(pmla)} | "
                      f"FATF {typos[0]['code'] if typos else 'N/A'} | "
                      f"FIU-IND STR Guidelines")

        ctx.set_recommendation(action, confidence, reasoning, reg_basis)
        logger.info(f"[Agent6] {action} — {confidence:.1%}")
        return ctx

    def _action(self, prob, watchlist, str_req, network, disagree) -> str:
        if watchlist and prob >= 0.5: return "BLOCK"
        if watchlist:                 return "FILE_STR"
        if prob >= 0.85:              return "BLOCK"
        if prob >= 0.65 or str_req:   return "FILE_STR"
        if disagree and prob >= 0.4:  return "ESCALATE"
        if prob >= 0.50 or network:   return "ESCALATE"
        if prob >= 0.35:              return "MONITOR"
        if prob >= 0.20:              return "REQUEST_INFO"
        return "CLOSE"

    def _confidence(self, ctx: InvestigationContext) -> float:
        s = ctx.confidence_scores
        w = {"agent1_anomaly":0.35,"agent2_evidence":0.20,
             "agent3_network":0.15,"agent4_regulatory":0.20,
             "agent5_explanation":0.10}
        score = sum(s.get(k,0.5)*v for k,v in w.items())
        if ctx.disagreement_flag: score *= 0.85
        return round(min(score + 0.1, 0.99), 4)

    def _reasoning(self, action, prob, typos, patterns, network, ctx) -> str:
        parts = [f"XGBoost={ctx.anomaly_scores.get('xgb_score',0):.2f}"]
        if typos:    parts.append(f"FATF {typos[0]['code']} ({typos[0]['name']})")
        if patterns: parts.append(f"Patterns: {', '.join(p.replace('_',' ') for p in patterns[:3])}")
        if network:  parts.append(f"{ctx.network.get('node_count',0)}-account ring, "
                                   f"{len(ctx.sub_cases)} sub-case(s)")
        if ctx.watchlist_hit:
            parts.append(f"Watchlist: {', '.join(h['entity'] for h in ctx.watchlist_hits[:2])}")
        if ctx.disagreement_flag: parts.append("Model disagreement — novel pattern")
        if ctx.shap_values:
            t = ctx.shap_values[0]
            parts.append(f"Top driver: {t['feature'].replace('_',' ')} ({t['value']:+.3f})")
        return f"{action}: " + " | ".join(parts)
