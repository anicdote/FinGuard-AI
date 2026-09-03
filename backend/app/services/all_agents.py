"""
FinGuard AI — All 6 Agents
────────────────────────────
All agents in one file for simplicity.
Import: from app.services.all_agents import Agent1Anomaly, Agent2Evidence, etc.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

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
    """Bounded, deterministic one-hop network analysis backed by transactions."""
    LOOKBACK_DAYS = 30
    HISTORY_LIMIT_PER_ENDPOINT = 100
    MAX_HISTORY_TRANSACTIONS = 200

    def __init__(self, transaction_repository=None):
        self.transaction_repository = transaction_repository

    async def run(self, ctx: InvestigationContext) -> InvestigationContext:
        history = await self._history(ctx.transaction, ctx.transaction_id)
        nodes, edges, evidence = self._graph(ctx.transaction, history)
        clusters = self._find_clusters(nodes, edges)
        evidence["strongly_connected_components"] = {
            "count": len(clusters),
            "cyclic_component_count": sum(c["node_count"] > 1 for c in clusters),
            "largest_component_size": max((c["node_count"] for c in clusters), default=0),
        }
        evidence["provisional_network_risk_score"] = self._provisional_network_risk(evidence)
        primary = str(ctx.transaction.get("account_id", ""))
        sub_cases = self._sub_cases(nodes, primary)
        central = max(nodes, key=lambda n: (n["pagerank"], n["account_id"]), default={})
        network = {
            "node_count": len(nodes), "edge_count": len(edges), "nodes": nodes,
            "edges": edges, "scc_clusters": clusters,
            "max_pagerank": max((n["pagerank"] for n in nodes), default=0.0),
            "central_node": central.get("account_id", ""), "evidence": evidence,
        }
        ctx.set_network(network, sub_cases)
        return ctx

    async def _history(self, focal: dict, transaction_id: str) -> List[dict]:
        """Read only the focal endpoints, in the inclusive prior 30-day window."""
        end = self._timestamp(focal.get("timestamp"))
        if not self.transaction_repository or not end:
            return []
        focal_id, records = str(focal.get("_id", transaction_id or "")), {}
        endpoints = sorted({str(v) for v in (focal.get("account_id"), focal.get("counterpartyAccount")) if v})
        for account in endpoints:
            found = await self.transaction_repository.get_by_account_roles(
                account, start=end - timedelta(days=self.LOOKBACK_DAYS), end=end,
                limit=self.HISTORY_LIMIT_PER_ENDPOINT, exclude_transaction_id=focal_id or None,
            )
            for item in found:
                item_id = str(item.get("_id", ""))
                if item_id and item_id != focal_id:
                    records[item_id] = item
        result = list(records.values())
        result.sort(key=lambda x: (self._timestamp(x.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc), str(x.get("_id", ""))))
        return result[:self.MAX_HISTORY_TRANSACTIONS]

    def _graph(self, focal: dict, history: List[dict]):
        records, edges = [focal] + history, []
        for item in records:
            source, destination = item.get("account_id"), item.get("counterpartyAccount")
            if source and destination:
                edges.append({"from": str(source), "to": str(destination),
                              "amount": float(item.get("amount") or 0.0),
                              "timestamp": item.get("timestamp"), "channel": item.get("channel"),
                              "transaction_id": str(item.get("_id", ""))})
        edges.sort(key=lambda e: (self._timestamp(e["timestamp"]) or datetime.min.replace(tzinfo=timezone.utc), e["transaction_id"], e["from"], e["to"]))
        accounts = sorted({e[key] for e in edges for key in ("from", "to")})
        metrics = self._metrics(accounts, edges, records)
        ranks = self._pagerank(accounts, edges)
        max_transactions = max((m["transaction_count"] for m in metrics.values()), default=0)
        max_degree = max((m["in_degree"] + m["out_degree"] for m in metrics.values()), default=0)
        max_volume = max((m["total_inflow"] + m["total_outflow"] for m in metrics.values()), default=0.0)
        max_pagerank = max(ranks.values(), default=0.0)
        primary = str(focal.get("account_id", ""))
        nodes = [self._node(
            a, metrics[a], a == primary, ranks[a], max_transactions,
            max_degree, max_volume, max_pagerank,
        ) for a in accounts]
        return nodes, edges, self._evidence(edges, records, metrics, primary, ranks)

    def _metrics(self, accounts, edges, records):
        result = {a: {"in_degree": 0, "out_degree": 0, "total_inflow": 0.0,
                      "total_outflow": 0.0, "transaction_count": 0,
                      "suspicious_transaction_count": 0} for a in accounts}
        by_id = {str(item.get("_id", "")): item for item in records}
        for edge in edges:
            source, destination, amount = edge["from"], edge["to"], edge["amount"]
            result[source]["out_degree"] += 1; result[source]["total_outflow"] += amount
            result[destination]["in_degree"] += 1; result[destination]["total_inflow"] += amount
            suspicious = self._is_suspicious(by_id.get(edge["transaction_id"], {}))
            for account in {source, destination}:
                result[account]["transaction_count"] += 1
                result[account]["suspicious_transaction_count"] += int(suspicious)
        pairs = {(edge["from"], edge["to"]) for edge in edges}
        for account in accounts:
            result[account]["reciprocal_relationship_count"] = sum(
                1 for source, destination in pairs
                if source == account and source != destination and (destination, source) in pairs
            )
        return result

    def _pagerank(self, accounts, edges):
        if not accounts: return {}
        count, damping = len(accounts), 0.85
        outgoing = {a: [] for a in accounts}
        for edge in edges: outgoing[edge["from"]].append(edge)
        ranks = {a: 1.0 / count for a in accounts}
        for _ in range(100):
            dangling = sum(ranks[a] for a in accounts if not outgoing[a]) / count
            next_ranks = {}
            for account in accounts:
                inbound = 0.0
                for edge in (e for e in edges if e["to"] == account):
                    source_edges = outgoing[edge["from"]]
                    total = sum(max(e["amount"], 0.0) for e in source_edges)
                    share = edge["amount"] / total if total else 1.0 / len(source_edges)
                    inbound += ranks[edge["from"]] * share
                next_ranks[account] = (1 - damping) / count + damping * (inbound + dangling)
            if max(abs(next_ranks[a] - ranks[a]) for a in accounts) < 1e-12:
                return next_ranks
            ranks = next_ranks
        return ranks

    def _node(self, account, metric, is_primary, pagerank, max_transactions,
              max_degree, max_volume, max_pagerank):
        """Score observable account behavior; labels remain diagnostic evidence only."""
        activity = metric["transaction_count"] / max_transactions if max_transactions else 0.0
        connectivity = (metric["in_degree"] + metric["out_degree"]) / max_degree if max_degree else 0.0
        volume = (metric["total_inflow"] + metric["total_outflow"]) / max_volume if max_volume else 0.0
        centrality = pagerank / max_pagerank if max_pagerank else 0.0
        reciprocal = float(metric["reciprocal_relationship_count"] > 0)
        # Emphasize bidirectional movement, then normalize observed activity,
        # connectivity, transaction value, and graph centrality within this
        # bounded one-hop network.  Every component is in [0, 1].
        risk = round(min(1.0, .50 * reciprocal + .15 * activity + .10 * connectivity +
                             .15 * volume + .10 * centrality), 4)
        level = "critical" if risk >= .85 else "high" if risk >= .65 else "medium" if risk >= .4 else "low"
        return {"account_id": account, "risk_score": risk, "risk_level": level,
                "is_primary": is_primary, "pagerank": round(pagerank, 8),
                "degree": metric["in_degree"] + metric["out_degree"],
                "in_degree": metric["in_degree"], "out_degree": metric["out_degree"],
                "weighted_degree": round(metric["total_inflow"] + metric["total_outflow"], 4),
                "transaction_count": metric["transaction_count"],
                "suspicious_transaction_count": metric["suspicious_transaction_count"],
                "reciprocal_relationship_count": metric["reciprocal_relationship_count"],
                "total_inflow": round(metric["total_inflow"], 4), "total_outflow": round(metric["total_outflow"], 4)}

    def _find_clusters(self, nodes, edges):
        graph = {n["account_id"]: [] for n in nodes}; reverse = {n["account_id"]: [] for n in nodes}
        for edge in edges: graph[edge["from"]].append(edge["to"]); reverse[edge["to"]].append(edge["from"])
        visited, order = set(), []
        def visit(a):
            visited.add(a)
            for b in sorted(graph[a]):
                if b not in visited: visit(b)
            order.append(a)
        for a in sorted(graph):
            if a not in visited: visit(a)
        risks, components = {n["account_id"]: n["risk_score"] for n in nodes}, []
        visited.clear()
        def collect(a, component):
            visited.add(a); component.append(a)
            for b in sorted(reverse[a]):
                if b not in visited: collect(b, component)
        for a in reversed(order):
            if a not in visited:
                component = []; collect(a, component); components.append(sorted(component))
        components.sort(key=lambda c: c[0])
        return [{"cluster_id": f"SCC-{i}", "node_count": len(c), "account_ids": c,
                 "avg_risk": round(sum(risks[a] for a in c) / len(c), 4)} for i, c in enumerate(components, 1)]

    def _evidence(self, edges, records, metrics, primary, ranks):
        count = len(edges)
        suspicious = sum(
            self._is_suspicious(item)
            for item in records
            if item.get("account_id") and item.get("counterpartyAccount")
        )
        pairs = {(e["from"], e["to"]) for e in edges}
        counterparties = {e["to"] for e in edges if e["from"] == primary} | {e["from"] for e in edges if e["to"] == primary}
        concentration = max((m["transaction_count"] for m in metrics.values()), default=0) / (2 * count) if count else 0.0
        return {"transaction_count": count, "total_network_transaction_volume": round(sum(e["amount"] for e in edges), 4),
                "suspicious_transaction_count": suspicious, "suspicious_transaction_ratio": round(suspicious / count, 4) if count else 0.0,
                "distinct_counterparty_count": len(counterparties), "activity_concentration": round(concentration, 4),
                "reciprocal_relationship_count": sum(1 for a, b in pairs if a < b and (b, a) in pairs),
                "primary_network_degree": metrics.get(primary, {}).get("in_degree", 0) + metrics.get(primary, {}).get("out_degree", 0),
                "max_network_degree": max((m["in_degree"] + m["out_degree"] for m in metrics.values()), default=0),
                "primary_pagerank": round(ranks.get(primary, 0.0), 8),
                "max_pagerank": round(max(ranks.values(), default=0.0), 8)}

    @staticmethod
    def _provisional_network_risk(evidence):
        degree = evidence["primary_network_degree"] / evidence["max_network_degree"] if evidence["max_network_degree"] else 0.0
        centrality = evidence["primary_pagerank"] / evidence["max_pagerank"] if evidence["max_pagerank"] else 0.0
        return round(min(1.0, .45 * evidence["activity_concentration"] +
                         .30 * int(evidence["reciprocal_relationship_count"] > 0) +
                         .15 * degree + .10 * centrality), 4)

    def _sub_cases(self, nodes, primary):
        candidates = [n for n in nodes if n["account_id"] != primary and n["risk_score"] >= SUBCASES_THRESHOLD]
        candidates.sort(key=lambda n: (-n["risk_score"], -n["pagerank"], n["account_id"]))
        return [{"account_id": n["account_id"], "risk_score": n["risk_score"], "risk_level": n["risk_level"],
                 "reason": f"Elevated observed network behavior score {n['risk_score']:.2f} across {n['transaction_count']} transaction(s)", "auto_created": True} for n in candidates[:MAX_SUBCASES]]

    @staticmethod
    def _is_suspicious(transaction):
        is_fraud = transaction.get("is_fraud")
        normalized_is_fraud = is_fraud.strip().lower() if isinstance(is_fraud, str) else None
        return (
            is_fraud is True
            or (type(is_fraud) is int and is_fraud == 1)
            or normalized_is_fraud in {"1", "true"}
            or str(transaction.get("fraud_label", "")).strip().lower() in {"fraud", "suspicious"}
        )

    @staticmethod
    def _timestamp(value):
        if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError: return None
        return None


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
