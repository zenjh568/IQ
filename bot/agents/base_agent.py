"""Base agent interface."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    action: str          # "call", "put", or "wait"
    confidence: float    # 0.0 – 1.0
    reason: str
    agent_name: str
    indicators: Dict = field(default_factory=dict)


class BaseAgent(ABC):
    """
    All trading agents inherit from this class.

    Subclasses must implement `analyze()` which receives the latest candle
    data and returns a Signal.
    """

    name: str = "BaseAgent"
    description: str = ""

    def __init__(self, config: dict):
        self.config = config
        self.enabled: bool = config.get("enabled", True)
        self.min_confidence: float = config.get("min_confidence", 0.6)
        self._history: List[Signal] = []

    @abstractmethod
    def analyze(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        """Analyse the given OHLC series and return a Signal."""

    def get_signal(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Signal:
        if not self.enabled:
            return Signal("wait", 0.0, "agent disabled", self.name)
        try:
            sig = self.analyze(opens, highs, lows, closes)
        except Exception as exc:
            logger.exception("Agent %s raised: %s", self.name, exc)
            sig = Signal("wait", 0.0, f"error: {exc}", self.name)
        self._history.append(sig)
        if len(self._history) > 200:
            self._history = self._history[-200:]
        return sig

    @property
    def last_signal(self) -> Optional[Signal]:
        return self._history[-1] if self._history else None

    @property
    def win_rate(self) -> float:
        """Placeholder – actual win rate is tracked by the trade manager."""
        return 0.0
