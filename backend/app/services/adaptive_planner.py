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
    """Orchestrates the six-agent investigation pipeline dynamically."""

    def __init__(self, transaction_repository=None):
        from app.services.all_agents import (
            Agent1Anomaly, Agent2Evidence, Agent3Network,
            Agent4Regulatory, Agent5Explanation,
        )
        from app.services.agent6_decision import Agent6Recommend

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

        ctx = await self._run("Agent1_Anomaly", ctx,
                              reason="Always run first — need anomaly score")
        ctx = await self._run("Agent2_Evidence", ctx,
                              reason="Always gather raw evidence")

        if ctx.needs_network_investigation:
            ctx = await self._run(
                "Agent3_Network", ctx,
                reason=f"Score={ctx.fraud_probability:.2f} >= 0.4 "
                       f"or watchlist_hit={ctx.watchlist_hit}"
            )
        else:
            logger.info("[Planner] Skipping Agent3_Network — score too low")
            ctx.agent_log.append({
                "agent": "Agent3_Network",
                "detail": f"SKIPPED — score={ctx.fraud_probability:.2f} < 0.4",
                "timestamp": "",
            })

        if ctx.is_high_risk or ctx.network.get("node_count", 0) > 0:
            ctx = await self._run(
                "Agent4_Regulatory", ctx,
                reason=f"is_high_risk={ctx.is_high_risk} "
                       f"network_nodes={ctx.network.get('node_count', 0)}"
            )
        else:
            ctx.agent_log.append({
                "agent": "Agent4_Regulatory",
                "detail": "SKIPPED — low risk, no network",
                "timestamp": "",
            })

        ctx = await self._run("Agent5_Explanation", ctx,
                              reason="Always generate explanation and STR")
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
            "agent": f"Planner→{agent_name}",
            "detail": f"Invoking. Reason: {reason}",
            "timestamp": now,
        })
        try:
            result = self.agents[agent_name].run(ctx)
            ctx = await result if hasattr(result, "__await__") else result
        except Exception as e:
            logger.error(f"[Planner] {agent_name} failed: {e}", exc_info=True)
            ctx.agent_log.append({
                "agent": agent_name,
                "detail": f"ERROR: {e}",
                "timestamp": now,
            })
        return ctx


_planner_instance: Optional[AdaptivePlanner] = None


def get_planner(transaction_repository=None) -> AdaptivePlanner:
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = AdaptivePlanner(transaction_repository)
    elif transaction_repository is not None:
        _planner_instance.agents["Agent3_Network"].transaction_repository = transaction_repository
    return _planner_instance
