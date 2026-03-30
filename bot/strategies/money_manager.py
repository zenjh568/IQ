"""
Money-management strategies that modify the bet amount based on trade history.

Supported strategies:
    flat        – fixed percentage of balance (default)
    martingale  – double after loss, reset after win
    anti_martingale – double after win, reset after loss (also called Paroli)
    soros       – reinvest winnings progressively (George Soros inspired)
    fibonacci   – follow Fibonacci sequence on losses
"""
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class MoneyManager:
    """
    Wraps the base bet calculation from RiskManager and applies a compounding
    strategy on top.

    Configuration keys:
        strategy        (str)   one of: flat, martingale, anti_martingale, soros, fibonacci
        base_bet        (float) starting bet (overrides balance %)
        martingale_max  (int)   maximum martingale doublings, default 4
        soros_cycles    (int)   number of winning cycles before reset, default 3
    """

    STRATEGIES = ("flat", "martingale", "anti_martingale", "soros", "fibonacci")

    def __init__(self, config: dict):
        self.config = config
        self.strategy: str = config.get("strategy", "flat")
        self.base_bet: float = config.get("base_bet", 1.0)
        self.martingale_max: int = config.get("martingale_max", 4)
        self.soros_cycles: int = config.get("soros_cycles", 3)

        self._current_bet: float = self.base_bet
        self._level: int = 0              # martingale / fibonacci level
        self._soros_profit: float = 0.0   # accumulated profit to reinvest
        self._soros_cycle: int = 0        # current soros cycle count
        self._fib: List[float] = self._build_fib(self.martingale_max + 2)
        self._win_streak: int = 0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def next_bet(self, balance: float, min_bet: float, max_bet: float) -> float:
        """Return the bet for the *next* trade (before the trade is placed)."""
        if self.strategy == "flat":
            bet = self.base_bet
        elif self.strategy == "martingale":
            bet = self._current_bet
        elif self.strategy == "anti_martingale":
            bet = self._current_bet
        elif self.strategy == "soros":
            bet = self.base_bet + self._soros_profit
        elif self.strategy == "fibonacci":
            idx = min(self._level, len(self._fib) - 1)
            bet = self.base_bet * self._fib[idx]
        else:
            bet = self.base_bet

        return round(max(min_bet, min(max_bet, bet)), 2)

    def record_result(self, won: bool, profit: float):
        """Update internal state after a trade closes."""
        if self.strategy == "martingale":
            if won:
                self._current_bet = self.base_bet
                self._level = 0
            else:
                self._level = min(self._level + 1, self.martingale_max)
                self._current_bet = min(
                    self.base_bet * (2 ** self._level),
                    self.config.get("max_bet", 100.0),
                )

        elif self.strategy == "anti_martingale":
            if won:
                self._win_streak += 1
                self._current_bet = min(
                    self.base_bet * (2 ** self._win_streak),
                    self.config.get("max_bet", 100.0),
                )
            else:
                self._win_streak = 0
                self._current_bet = self.base_bet

        elif self.strategy == "soros":
            if won:
                self._soros_cycle += 1
                self._soros_profit += profit
                if self._soros_cycle >= self.soros_cycles:
                    # bank the profits and start fresh
                    self._soros_profit = 0.0
                    self._soros_cycle = 0
            else:
                self._soros_profit = 0.0
                self._soros_cycle = 0

        elif self.strategy == "fibonacci":
            if won:
                self._level = max(0, self._level - 2)
            else:
                self._level = min(self._level + 1, len(self._fib) - 1)

        else:  # flat
            pass

    def reset(self):
        self._current_bet = self.base_bet
        self._level = 0
        self._soros_profit = 0.0
        self._soros_cycle = 0
        self._win_streak = 0

    @property
    def current_level(self) -> int:
        return self._level

    @property
    def strategy_info(self) -> str:
        if self.strategy == "martingale":
            return f"Martingale L{self._level} (bet ${self._current_bet:.2f})"
        if self.strategy == "anti_martingale":
            return f"Anti-Martingale streak={self._win_streak}"
        if self.strategy == "soros":
            return f"Soros cycle={self._soros_cycle} profit=${self._soros_profit:.2f}"
        if self.strategy == "fibonacci":
            return f"Fibonacci L{self._level}"
        return "Flat"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fib(n: int) -> List[float]:
        seq = [1.0, 1.0]
        while len(seq) < n:
            seq.append(seq[-1] + seq[-2])
        return seq
