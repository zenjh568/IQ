"""
Signal filter – validates and aggregates signals from multiple agents
before forwarding a trade recommendation to the executor.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from bot.agents.base_agent import Signal

logger = logging.getLogger(__name__)


class SignalFilter:
    """
    Receives signals from all active agents and decides whether to act.

    Modes:
        majority    – trade when the majority of agents agree
        unanimous   – trade only when ALL agents agree
        weighted    – weighted vote; threshold configurable
        best        – follow the agent with the highest confidence

    Configuration keys:
        mode                (str)   majority | unanimous | weighted | best
        confidence_threshold (float) minimum confidence to act, default 0.60
        agent_weights       (dict)  {agent_name: weight} for weighted mode
    """

    def __init__(self, config: dict):
        self.mode: str = config.get("mode", "majority")
        self.confidence_threshold: float = config.get("confidence_threshold", 0.60)
        self.agent_weights: Dict[str, float] = config.get("agent_weights", {})

    def filter(self, signals: List[Signal]) -> Optional[Signal]:
        """
        Aggregate *signals* and return a single Signal or None if we should wait.
        """
        if not signals:
            return None

        # Remove "wait" signals that have 0 confidence
        active = [s for s in signals if s.action in ("call", "put")]
        if not active:
            return None

        if self.mode == "best":
            best = max(active, key=lambda s: s.confidence)
            if best.confidence >= self.confidence_threshold:
                return best
            return None

        if self.mode == "unanimous":
            actions = {s.action for s in active}
            if len(actions) == 1 and len(active) == len(signals):
                agg = self._aggregate(active)
                if agg.confidence >= self.confidence_threshold:
                    return agg
            return None

        if self.mode == "weighted":
            call_weight = sum(
                s.confidence * self.agent_weights.get(s.agent_name, 1.0)
                for s in active if s.action == "call"
            )
            put_weight = sum(
                s.confidence * self.agent_weights.get(s.agent_name, 1.0)
                for s in active if s.action == "put"
            )
            total = call_weight + put_weight
            if total == 0:
                return None
            if call_weight > put_weight:
                conf = call_weight / total
                if conf >= self.confidence_threshold:
                    reasons = [s.reason for s in active if s.action == "call"]
                    return Signal("call", conf, " | ".join(reasons), "SignalFilter",
                                  {"call_w": round(call_weight, 2), "put_w": round(put_weight, 2)})
            else:
                conf = put_weight / total
                if conf >= self.confidence_threshold:
                    reasons = [s.reason for s in active if s.action == "put"]
                    return Signal("put", conf, " | ".join(reasons), "SignalFilter",
                                  {"call_w": round(call_weight, 2), "put_w": round(put_weight, 2)})
            return None

        # Default: majority
        calls = [s for s in active if s.action == "call"]
        puts = [s for s in active if s.action == "put"]

        if len(calls) > len(puts) and len(calls) > len(active) / 2:
            agg = self._aggregate(calls)
            if agg.confidence >= self.confidence_threshold:
                return agg
        elif len(puts) > len(calls) and len(puts) > len(active) / 2:
            agg = self._aggregate(puts)
            if agg.confidence >= self.confidence_threshold:
                return agg

        return None

    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate(signals: List[Signal]) -> Signal:
        avg_conf = sum(s.confidence for s in signals) / len(signals)
        action = signals[0].action
        reasons = " | ".join(s.reason for s in signals)
        names = ", ".join(s.agent_name for s in signals)
        return Signal(action, avg_conf, reasons, f"[{names}]")
