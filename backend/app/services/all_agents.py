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

FATF_TYPOLOGIES = {
    "T1_Structuring": {
        "name": "Structuring / Smurfing",
        "description": "Breaking large amounts into smaller transactions to avoid reporting thresholds",
        "pmla_section": "Section 3 & Section 12(1)(a)",
        "indicators": ["structuring_near_ctr", "round_amount", "multiple_transactions"],
        "severity": 0.85,
    },
    "T2_TBML": {
        "name": "Trade-Based Money Laundering",
        "description": "Using international trade transactions to move illicit funds",
        "pmla_section": "Section 3",
        "indicators": ["high_risk_channel", "international_transfer"],
        "severity": 0.80,
    },
    "T3_Layering": {
        "name": "Layering",
        "description": "Complex series of transactions to disguise origin of funds",
        "pmla_section": "Section 3 & Section 4",
        "indicators": ["complete_balance_drain", "high_risk_channel", "above_ctr_threshold"],
        "severity": 0.90,
    },
    "T4_CyberFraud": {
        "name": "Cyber-Enabled Fraud",
        "description": "Account takeover, SIM-swap, or digital fraud patterns",
        "pmla_section": "Section 3",
        "indicators": ["night_hour_transaction", "high_risk_channel", "complete_balance_drain"],
        "severity": 0.75,
    },
    "T5_CashIntensive": {
        "name": "Cash-Intensive Business",
        "description": "Unusually high cash transactions inconsistent with account profile",
        "pmla_section": "Section 12(1)(a)",
        "indicators": ["above_ctr_threshold", "round_amount"],
        "severity": 0.70,
    },
}


class Agent4Regulatory:
    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        logger.info(f"[Agent4] Regulatory assessment for {ctx.transaction_id}")
        patterns    = ctx.evidence.get("patterns", [])
        prob        = ctx.fraud_probability
        has_network = ctx.network.get("node_count", 0) > 2

        matched     = []
        pmla_secs   = set()
        max_sev     = 0.0

        for code, typo in FATF_TYPOLOGIES.items():
            hits = sum(1 for ind in typo["indicators"] if ind in patterns)
            if prob >= 0.7 and code == "T3_Layering":          hits += 1
            if has_network and code == "T3_Layering":          hits += 1
            if ctx.watchlist_hit and code in ("T2_TBML","T3_Layering"): hits += 2

            if hits >= 1:
                conf = min(hits / len(typo["indicators"]) * 0.9 + 0.1, 0.99)
                matched.append({"code": code, "name": typo["name"],
                                 "description": typo["description"],
                                 "confidence": round(conf, 3),
                                 "severity": typo["severity"],
                                 "pmla": typo["pmla_section"]})
                pmla_secs.add(typo["pmla_section"])
                max_sev = max(max_sev, typo["severity"])

        matched.sort(key=lambda x: x["confidence"], reverse=True)
        reg_conf = (sum(t["confidence"] for t in matched) / len(matched)
                    if matched else 0.3)

        ctx.set_regulatory({
            "fatf_typologies":       matched,
            "primary_typology":      matched[0] if matched else None,
            "pmla_sections":         list(pmla_secs),
            "regulatory_confidence": round(reg_conf, 3),
            "max_severity":          round(max_sev, 3),
            "fiu_ind_reportable":    prob >= 0.5 or bool(matched),
            "str_required":          prob >= 0.7 or max_sev >= 0.80,
        })
        logger.info(f"[Agent4] typologies={[t['code'] for t in matched]}")
        return ctx


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
