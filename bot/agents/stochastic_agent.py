"""Stochastic oscillator trading agent."""
from __future__ import annotations

from typing import List

from bot.agents.base_agent import BaseAgent, Signal
from bot.utils.indicators import stochastic, trend_direction


class StochasticAgent(BaseAgent):
    """
    Signals when %K/%D cross in oversold/overbought territory, optionally
    confirmed by the EMA trend.

    Configuration keys:
        k_period    (int)   %K period, default 14
        d_period    (int)   %D smoothing, default 3
        oversold    (float) threshold below which we look for calls, default 20
        overbought  (float) threshold above which we look for puts, default 80
    """

    name = "Stochastic Agent"
    description = "Momentum: %K/%D crossover at extremes"

    def analyze(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        k_period = self.config.get("k_period", 14)
        d_period = self.config.get("d_period", 3)
        oversold = self.config.get("oversold", 20)
        overbought = self.config.get("overbought", 80)

        k, d = stochastic(highs, lows, closes, k_period, d_period)
        if k is None:
            return Signal("wait", 0.0, "not enough data", self.name)

        trend = trend_direction(closes)
        indicators = {"stoch_k": round(k, 2), "stoch_d": round(d, 2), "trend": trend}

        # Previous bar stoch
        if len(closes) >= k_period + d_period + 1:
            k_prev, d_prev = stochastic(highs[:-1], lows[:-1], closes[:-1], k_period, d_period)
        else:
            k_prev, d_prev = None, None

        # Bullish cross in oversold zone
        if k <= oversold and d <= oversold:
            if k_prev and d_prev and k_prev < d_prev and k >= d:
                confidence = 0.70 if trend != "DOWN" else 0.55
                return Signal("call", confidence, f"%K crossed above %D in oversold zone ({k:.1f})",
                              self.name, indicators)

        # Bearish cross in overbought zone
        if k >= overbought and d >= overbought:
            if k_prev and d_prev and k_prev > d_prev and k <= d:
                confidence = 0.70 if trend != "UP" else 0.55
                return Signal("put", confidence, f"%K crossed below %D in overbought zone ({k:.1f})",
                              self.name, indicators)

        return Signal("wait", 0.0, f"Stoch %K={k:.1f} – no cross signal", self.name, indicators)
