"""
Technical indicators used by trading agents.
All functions operate on plain Python lists or produce plain numbers,
so there is no hard dependency on pandas.
"""
from __future__ import annotations

from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ema(values: List[float], period: int) -> List[float]:
    """Exponential moving average (wilder smoothing where alpha = 2/(n+1))."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    result: List[float] = []
    seed = sum(values[:period]) / period
    result.append(seed)
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def _sma(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    return [sum(values[i : i + period]) / period for i in range(len(values) - period + 1)]


# ---------------------------------------------------------------------------
# Public indicators
# ---------------------------------------------------------------------------

def rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Return the most-recent RSI value or None if not enough data."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def macd(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (macd_line, signal_line, histogram) or (None, None, None)."""
    if len(closes) < slow + signal:
        return None, None, None
    fast_ema = _ema(closes, fast)
    slow_ema = _ema(closes, slow)
    # align
    offset = slow - fast
    macd_line = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
    if len(macd_line) < signal:
        return None, None, None
    sig_line = _ema(macd_line, signal)
    if not sig_line:
        return None, None, None
    m = macd_line[-1]
    s = sig_line[-1]
    return m, s, m - s


def bollinger_bands(
    closes: List[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (upper, middle, lower) bands or (None, None, None)."""
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = variance ** 0.5
    return middle + std_dev * std, middle, middle - std_dev * std


def stochastic(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    k_period: int = 14,
    d_period: int = 3,
) -> Tuple[Optional[float], Optional[float]]:
    """Return (%K, %D) or (None, None)."""
    if len(closes) < k_period + d_period:
        return None, None
    k_values: List[float] = []
    for i in range(k_period - 1, len(closes)):
        hh = max(highs[i - k_period + 1 : i + 1])
        ll = min(lows[i - k_period + 1 : i + 1])
        if hh == ll:
            k_values.append(50.0)
        else:
            k_values.append(100 * (closes[i] - ll) / (hh - ll))
    if len(k_values) < d_period:
        return None, None
    d = sum(k_values[-d_period:]) / d_period
    return k_values[-1], d


def atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> Optional[float]:
    """Average True Range."""
    if len(closes) < period + 1:
        return None
    trs: List[float] = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return None
    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def ema_value(closes: List[float], period: int) -> Optional[float]:
    """Return the latest EMA value."""
    result = _ema(closes, period)
    return result[-1] if result else None


def williams_r(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> Optional[float]:
    """Williams %R oscillator."""
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return -50.0
    return -100 * (hh - closes[-1]) / (hh - ll)


def trend_direction(closes: List[float], short: int = 9, long_: int = 21) -> Optional[str]:
    """'UP', 'DOWN', or 'NEUTRAL' based on EMA crossover."""
    s = ema_value(closes, short)
    l = ema_value(closes, long_)
    if s is None or l is None:
        return None
    if s > l * 1.0002:
        return "UP"
    if s < l * 0.9998:
        return "DOWN"
    return "NEUTRAL"


def candle_pattern(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Optional[str]:
    """Detect simple one- and two-candle reversal patterns.

    Returns
    -------
    str or None
        ``'bullish'`` – price likely to rise.
        ``'bearish'`` – price likely to fall.
        ``None``      – no recognisable pattern.
    """
    if len(closes) < 3:
        return None

    # Current and previous candle
    o1, h1, l1, c1 = opens[-2], highs[-2], lows[-2], closes[-2]
    o2, h2, l2, c2 = opens[-1], highs[-1], lows[-1], closes[-1]

    body1 = abs(c1 - o1)
    body2 = abs(c2 - o2)
    range2 = (h2 - l2) if h2 != l2 else 1e-10
    lower_shadow2 = min(o2, c2) - l2
    upper_shadow2 = h2 - max(o2, c2)

    # ── Bullish engulfing ────────────────────────────────────────────────────
    if c1 < o1 and c2 > o2 and o2 <= c1 and c2 >= o1:
        return "bullish"

    # ── Bearish engulfing ────────────────────────────────────────────────────
    if c1 > o1 and c2 < o2 and o2 >= c1 and c2 <= o1:
        return "bearish"

    # ── Hammer (bullish reversal) ────────────────────────────────────────────
    if body2 > 0 and lower_shadow2 >= 2 * body2 and upper_shadow2 <= body2 * 0.5:
        return "bullish"

    # ── Shooting star (bearish reversal) ────────────────────────────────────
    if body2 > 0 and upper_shadow2 >= 2 * body2 and lower_shadow2 <= body2 * 0.5:
        return "bearish"

    # ── Doji followed by directional move ───────────────────────────────────
    if body1 < range2 * 0.1 and body2 > range2 * 0.5:
        return "bullish" if c2 > o2 else "bearish"

    # ── Three consecutive same-direction closes ──────────────────────────────
    if len(closes) >= 4:
        # All three candles must be bullish (close > open) and ascending closes
        if (closes[-3] < closes[-2] < closes[-1]
                and opens[-3] < closes[-3]
                and opens[-2] < closes[-2]
                and opens[-1] < closes[-1]):
            return "bullish"
        # All three candles must be bearish (close < open) and descending closes
        if (closes[-3] > closes[-2] > closes[-1]
                and opens[-3] > closes[-3]
                and opens[-2] > closes[-2]
                and opens[-1] > closes[-1]):
            return "bearish"

    return None


def candles_to_ohlc(candles: list) -> Tuple[List, List, List, List]:
    opens, highs, lows, closes = [], [], [], []
    for c in candles:
        opens.append(float(c.get("open", c.get("o", 0))))
        highs.append(float(c.get("max", c.get("h", 0))))
        lows.append(float(c.get("min", c.get("l", 0))))
        closes.append(float(c.get("close", c.get("c", 0))))
    return opens, highs, lows, closes
