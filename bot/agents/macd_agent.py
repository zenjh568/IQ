"""MACD crossover trading agent."""
from __future__ import annotations

from typing import List

from bot.agents.base_agent import BaseAgent, Signal
from bot.utils.indicators import macd, rsi


class MACDAgent(BaseAgent):
    """
    Signals on MACD line / signal line crossovers, optionally filtered
    by RSI to avoid entering in exhausted moves.

    Configuration keys:
        fast        (int)   fast EMA period, default 12
        slow        (int)   slow EMA period, default 26
        signal      (int)   signal EMA period, default 9
        rsi_filter  (bool)  skip signal if RSI is extreme, default True
    """

    name = "MACD Agent"
    description = "Trend-following crossover strategy"

    def analyze(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        fast = self.config.get("fast", 12)
        slow = self.config.get("slow", 26)
        signal_p = self.config.get("signal", 9)
        rsi_filter = self.config.get("rsi_filter", True)

        if len(closes) < 2:
            return Signal("wait", 0.0, "not enough data", self.name)

        # current and previous bar values
        macd_now, sig_now, hist_now = macd(closes, fast, slow, signal_p)
        macd_prev, sig_prev, hist_prev = macd(closes[:-1], fast, slow, signal_p)

        if macd_now is None or macd_prev is None:
            return Signal("wait", 0.0, "not enough data", self.name)

        rsi_val = rsi(closes, 14)
        indicators = {
            "macd": round(macd_now, 5),
            "signal": round(sig_now, 5),
            "histogram": round(hist_now, 5),
            "rsi": round(rsi_val, 2) if rsi_val else None,
        }

        # Bullish crossover: MACD crossed above signal
        if macd_prev < sig_prev and macd_now >= sig_now:
            if rsi_filter and rsi_val and rsi_val > 70:
                return Signal("wait", 0.0, "MACD bullish cross but RSI overbought", self.name, indicators)
            strength = min(abs(hist_now) / (abs(macd_now) + 1e-9), 1.0)
            confidence = 0.65 + strength * 0.20
            return Signal("call", confidence, "MACD bullish crossover", self.name, indicators)

        # Bearish crossover: MACD crossed below signal
        if macd_prev > sig_prev and macd_now <= sig_now:
            if rsi_filter and rsi_val and rsi_val < 30:
                return Signal("wait", 0.0, "MACD bearish cross but RSI oversold", self.name, indicators)
            strength = min(abs(hist_now) / (abs(macd_now) + 1e-9), 1.0)
            confidence = 0.65 + strength * 0.20
            return Signal("put", confidence, "MACD bearish crossover", self.name, indicators)

        return Signal("wait", 0.0, "No MACD crossover", self.name, indicators)
