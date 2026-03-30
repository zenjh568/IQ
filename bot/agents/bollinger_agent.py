"""Bollinger Bands mean-reversion trading agent."""
from __future__ import annotations

from typing import List

from bot.agents.base_agent import BaseAgent, Signal
from bot.utils.indicators import bollinger_bands, rsi, atr


class BollingerAgent(BaseAgent):
    """
    Mean-reversion strategy: buy when price touches the lower band and
    sell when it touches the upper band.  ATR filter skips low-volatility
    environments.

    Configuration keys:
        period      (int)   BB period, default 20
        std_dev     (float) band width in std-devs, default 2.0
        atr_min     (float) minimum ATR relative to price (fraction), default 0.001
    """

    name = "Bollinger Bands Agent"
    description = "Mean-reversion at band extremes"

    def analyze(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        period = self.config.get("period", 20)
        std_dev = self.config.get("std_dev", 2.0)
        atr_min = self.config.get("atr_min", 0.001)

        upper, middle, lower = bollinger_bands(closes, period, std_dev)
        if upper is None:
            return Signal("wait", 0.0, "not enough data", self.name)

        price = closes[-1]
        rsi_val = rsi(closes, 14)
        atr_val = atr(highs, lows, closes, 14)

        indicators = {
            "upper": round(upper, 5),
            "middle": round(middle, 5),
            "lower": round(lower, 5),
            "price": round(price, 5),
            "rsi": round(rsi_val, 2) if rsi_val else None,
            "atr": round(atr_val, 5) if atr_val else None,
        }

        # ATR filter – skip in very low volatility
        if atr_val and price > 0 and (atr_val / price) < atr_min:
            return Signal("wait", 0.0, "ATR too low – low volatility", self.name, indicators)

        band_width = upper - lower
        if band_width == 0:
            return Signal("wait", 0.0, "bands are flat", self.name, indicators)

        # Price near lower band → CALL
        if price <= lower:
            distance = (lower - price) / band_width
            rsi_bonus = 0.10 if (rsi_val and rsi_val < 35) else 0.0
            confidence = min(0.65 + distance * 0.25 + rsi_bonus, 1.0)
            return Signal("call", confidence, f"Price at lower BB ({price:.5f} ≤ {lower:.5f})",
                          self.name, indicators)

        # Price near upper band → PUT
        if price >= upper:
            distance = (price - upper) / band_width
            rsi_bonus = 0.10 if (rsi_val and rsi_val > 65) else 0.0
            confidence = min(0.65 + distance * 0.25 + rsi_bonus, 1.0)
            return Signal("put", confidence, f"Price at upper BB ({price:.5f} ≥ {upper:.5f})",
                          self.name, indicators)

        return Signal("wait", 0.0, "Price within bands", self.name, indicators)
