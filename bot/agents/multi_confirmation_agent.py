"""
Multi-Confirmation Agent – requires agreement from multiple sub-indicators
before generating a signal.  Provides the highest-quality (but rarer) signals.
"""
from __future__ import annotations

from typing import List

from bot.agents.base_agent import BaseAgent, Signal
from bot.utils.indicators import (
    rsi, macd, bollinger_bands, stochastic,
    trend_direction, ema_value, williams_r,
)


class MultiConfirmationAgent(BaseAgent):
    """
    Aggregates signals from RSI, MACD, Bollinger Bands, Stochastic and
    Williams %R.  A trade is taken only when a configurable minimum number
    of indicators agree.

    Configuration keys:
        min_confirmations   (int)   default 3
        weights             (dict)  optional per-indicator weights (default 1 each)
    """

    name = "Multi-Confirmation Agent"
    description = "High-confidence signals requiring consensus across ≥3 indicators"

    def analyze(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        min_conf = self.config.get("min_confirmations", 3)
        weights = self.config.get("weights", {})

        votes_call: float = 0.0
        votes_put: float = 0.0
        reasons: List[str] = []
        indicators: dict = {}

        # ── 1. RSI ──────────────────────────────────────────────────────────
        rsi_val = rsi(closes, 14)
        if rsi_val is not None:
            indicators["rsi"] = round(rsi_val, 2)
            w = weights.get("rsi", 1.0)
            if rsi_val < 30:
                votes_call += w
                reasons.append(f"RSI {rsi_val:.1f}<30")
            elif rsi_val > 70:
                votes_put += w
                reasons.append(f"RSI {rsi_val:.1f}>70")

        # ── 2. MACD ─────────────────────────────────────────────────────────
        m, s, h = macd(closes)
        if m is not None and len(closes) >= 2:
            m_prev, s_prev, _ = macd(closes[:-1])
            indicators["macd_hist"] = round(h, 6)
            w = weights.get("macd", 1.0)
            if m_prev is not None:
                if m_prev < s_prev and m >= s:
                    votes_call += w
                    reasons.append("MACD bull-cross")
                elif m_prev > s_prev and m <= s:
                    votes_put += w
                    reasons.append("MACD bear-cross")
            # histogram momentum
            if h > 0 and h > abs(m) * 0.05:
                votes_call += w * 0.5
            elif h < 0 and abs(h) > abs(m) * 0.05:
                votes_put += w * 0.5

        # ── 3. Bollinger Bands ───────────────────────────────────────────────
        upper, mid, lower = bollinger_bands(closes, 20, 2.0)
        if upper is not None:
            price = closes[-1]
            indicators["bb_upper"] = round(upper, 5)
            indicators["bb_lower"] = round(lower, 5)
            w = weights.get("bb", 1.0)
            if price <= lower:
                votes_call += w
                reasons.append(f"Price at lower BB")
            elif price >= upper:
                votes_put += w
                reasons.append(f"Price at upper BB")

        # ── 4. Stochastic ───────────────────────────────────────────────────
        k, d = stochastic(highs, lows, closes)
        if k is not None:
            indicators["stoch_k"] = round(k, 2)
            w = weights.get("stoch", 1.0)
            if k < 20 and d < 20:
                votes_call += w
                reasons.append(f"Stoch oversold ({k:.1f})")
            elif k > 80 and d > 80:
                votes_put += w
                reasons.append(f"Stoch overbought ({k:.1f})")

        # ── 5. Williams %R ──────────────────────────────────────────────────
        wr = williams_r(highs, lows, closes)
        if wr is not None:
            indicators["williams_r"] = round(wr, 2)
            w = weights.get("williams_r", 1.0)
            if wr < -80:
                votes_call += w
                reasons.append(f"Williams %R {wr:.1f} oversold")
            elif wr > -20:
                votes_put += w
                reasons.append(f"Williams %R {wr:.1f} overbought")

        # ── 6. EMA trend ────────────────────────────────────────────────────
        trend = trend_direction(closes)
        indicators["trend"] = trend
        w = weights.get("trend", 0.5)
        if trend == "UP":
            votes_call += w
        elif trend == "DOWN":
            votes_put += w

        # ── Decision ────────────────────────────────────────────────────────
        total = max(votes_call + votes_put, 1e-9)
        indicators["votes_call"] = round(votes_call, 2)
        indicators["votes_put"] = round(votes_put, 2)

        if votes_call >= min_conf and votes_call > votes_put:
            confidence = min(0.60 + (votes_call / total) * 0.40, 1.0)
            return Signal("call", confidence, " | ".join(reasons), self.name, indicators)

        if votes_put >= min_conf and votes_put > votes_call:
            confidence = min(0.60 + (votes_put / total) * 0.40, 1.0)
            return Signal("put", confidence, " | ".join(reasons), self.name, indicators)

        return Signal(
            "wait", 0.0,
            f"Insufficient consensus (call={votes_call:.1f}, put={votes_put:.1f}, need {min_conf})",
            self.name, indicators,
        )
