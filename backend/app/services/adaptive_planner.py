"""
Adaptive Investigation Planner
────────────────────────────────
Decides which agent to invoke next based on investigation state.
Not a fixed pipeline — routing depends on what each agent finds.
"""

import logging
from typing import Optional
from app.services.investigation_context import InvestigationContext

logger = logging.getLogger(__name__)


class AdaptivePlanner:
    """
    Orchestrates the 7-agent pipeline dynamically.

    Decision rules (in priority order):
    1. Always run Agent 1 (Anomaly) first — need a score to make any decision
    2. Always run Agent 2 (Evidence) — gather raw evidence
    3. If score >= 0.4 OR watchlist hit → run Agent 3 (Network)
    4. If is_high_risk OR network found → run Agent 4 (Regulatory)
    5. If regulatory done → run Agent 5 (Explanation + STR)
    6. Always run Agent 6 (Recommendation) last
    """

    def __init__(self, transaction_repository=None):
        from app.services.all_agents import (
            Agent1Anomaly, Agent2Evidence, Agent3Network,
            Agent4Regulatory, Agent5Explanation, Agent6Recommend
        )
        self.agents = {
            "Agent1_Anomaly":     Agent1Anomaly(),
            "Agent2_Evidence":    Agent2Evidence(),
            "Agent3_Network":     Agent3Network(transaction_repository),
            "Agent4_Regulatory":  Agent4Regulatory(),
            "Agent5_Explanation": Agent5Explanation(),
            "Agent6_Recommend":   Agent6Recommend(),
        }

    async def investigate(self, ctx: InvestigationContext) -> InvestigationContext:
        txn_id = ctx.transaction_id
        logger.info(f"[Planner] Starting investigation for {txn_id}")

        # Step 1: Anomaly Detection always first
        ctx = await self._run("Agent1_Anomaly", ctx,
                              reason="Always run first — need anomaly score")

        # Step 2: Evidence Gathering always
        ctx = await self._run("Agent2_Evidence", ctx,
                              reason="Always gather raw evidence")

        # Step 3: Network Investigation — conditional
        if ctx.needs_network_investigation:
            ctx = await self._run(
                "Agent3_Network", ctx,
                reason=f"Score={ctx.fraud_probability:.2f} >= 0.4 "
                       f"or watchlist_hit={ctx.watchlist_hit}"
            )
        else:
            logger.info(f"[Planner] Skipping Agent3_Network — score too low")
            ctx.agent_log.append({
                "agent":     "Agent3_Network",
                "detail":    f"SKIPPED — score={ctx.fraud_probability:.2f} < 0.4",
                "timestamp": "",
            })

        # Step 4: Regulatory — if high risk or network found
        if ctx.is_high_risk or ctx.network.get("node_count", 0) > 0:
            ctx = await self._run(
                "Agent4_Regulatory", ctx,
                reason=f"is_high_risk={ctx.is_high_risk} "
                       f"network_nodes={ctx.network.get('node_count', 0)}"
            )
        else:
            ctx.agent_log.append({
                "agent":  "Agent4_Regulatory",
                "detail": "SKIPPED — low risk, no network",
                "timestamp": "",
            })

        # Step 5: Explanation + STR always
        ctx = await self._run("Agent5_Explanation", ctx,
                              reason="Always generate explanation and STR")

        # Step 6: Recommendation always last
        ctx = await self._run("Agent6_Recommend", ctx,
                              reason="Final step — synthesise all findings")

        logger.info(
            f"[Planner] Done for {txn_id} — "
            f"recommendation: {ctx.recommendation.get('action', '?')} "
            f"({ctx.recommendation.get('confidence_pct', 0)}%)"
        )
        return ctx

    async def _run(self, agent_name: str, ctx: InvestigationContext,
                   reason: str = "") -> InvestigationContext:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(f"[Planner] → {agent_name} | {reason}")
        ctx.agent_log.append({
            "agent":     f"Planner→{agent_name}",
            "detail":    f"Invoking. Reason: {reason}",
            "timestamp": now,
        })
        try:
            ctx = await self.agents[agent_name].run(ctx)
        except Exception as e:
            logger.error(f"[Planner] {agent_name} failed: {e}")
            ctx.agent_log.append({
                "agent":     agent_name,
                "detail":    f"ERROR: {e}",
                "timestamp": now,
            })
        return ctx


_planner_instance: Optional[AdaptivePlanner] = None

def get_planner(transaction_repository=None) -> AdaptivePlanner:
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = AdaptivePlanner(transaction_repository)
    elif transaction_repository is not None:
        # The worker supplies its already-open repository; no second DB session.
        _planner_instance.agents["Agent3_Network"].transaction_repository = transaction_repository
    return _planner_instance
