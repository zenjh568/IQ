"""RSI-based trading agent."""
from __future__ import annotations

from typing import List

from bot.agents.base_agent import BaseAgent, Signal
from bot.utils.indicators import rsi, ema_value, trend_direction


class RSIAgent(BaseAgent):
    """
    Generates signals when RSI is oversold / overbought, confirmed by
    the short-term EMA trend direction.

    Configuration keys (all optional):
        period      (int)   RSI period, default 14
        oversold    (float) RSI below this → possible CALL, default 30
        overbought  (float) RSI above this → possible PUT,  default 70
        ema_confirm (bool)  require EMA trend confirmation, default True
    """

    name = "RSI Agent"
    description = "Momentum oscillator – trades oversold/overbought extremes"

    def analyze(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        period = self.config.get("period", 14)
        oversold = self.config.get("oversold", 30)
        overbought = self.config.get("overbought", 70)
        confirm = self.config.get("ema_confirm", True)

        rsi_val = rsi(closes, period)
        trend = trend_direction(closes)

        if rsi_val is None:
            return Signal("wait", 0.0, "not enough data", self.name,
                          {"rsi": None, "trend": trend})

        indicators = {"rsi": round(rsi_val, 2), "trend": trend}

        # --- oversold → CALL ------------------------------------------------
        if rsi_val <= oversold:
            if confirm and trend == "DOWN":
                confidence = 0.60
                reason = f"RSI {rsi_val:.1f} oversold (trend still down – lower confidence)"
            else:
                confidence = 0.75 + (oversold - rsi_val) / oversold * 0.25
                reason = f"RSI {rsi_val:.1f} oversold"
            return Signal("call", min(confidence, 1.0), reason, self.name, indicators)

        # --- overbought → PUT -----------------------------------------------
        if rsi_val >= overbought:
            if confirm and trend == "UP":
                confidence = 0.60
                reason = f"RSI {rsi_val:.1f} overbought (trend still up – lower confidence)"
            else:
                confidence = 0.75 + (rsi_val - overbought) / (100 - overbought) * 0.25
                reason = f"RSI {rsi_val:.1f} overbought"
            return Signal("put", min(confidence, 1.0), reason, self.name, indicators)

        return Signal("wait", 0.0, f"RSI {rsi_val:.1f} – neutral zone", self.name, indicators)
