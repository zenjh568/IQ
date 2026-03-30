"""
Risk manager – enforces daily loss limits, consecutive loss limits,
balance protection, and bet-size policies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    timestamp: datetime
    active: str
    action: str
    amount: float
    duration: int
    profit: Optional[float] = None   # None while open; filled when closed
    win: Optional[bool] = None


class RiskManager:
    """
    Central risk-management component.

    Configuration keys:
        max_daily_loss      (float)  maximum total loss allowed today (absolute $)
        max_consecutive_losses (int) stop after N consecutive losses
        balance_pct_per_trade (float) fraction of balance per trade, default 0.02
        min_bet             (float)  minimum bet amount, default 1.0
        max_bet             (float)  maximum bet amount, default 100.0
        daily_trade_limit   (int)    maximum trades per day, default 50
    """

    def __init__(self, config: dict):
        self.config = config
        self.max_daily_loss: float = config.get("max_daily_loss", 50.0)
        self.max_consecutive_losses: int = config.get("max_consecutive_losses", 5)
        self.balance_pct: float = config.get("balance_pct_per_trade", 0.02)
        self.min_bet: float = config.get("min_bet", 1.0)
        self.max_bet: float = config.get("max_bet", 100.0)
        self.daily_trade_limit: int = config.get("daily_trade_limit", 50)

        self.trades: List[TradeRecord] = []
        self._day_start_balance: float = 0.0
        self._tracking_date: date = date.today()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_balance(self, balance: float):
        if date.today() != self._tracking_date:
            self._tracking_date = date.today()
            self._day_start_balance = balance
        elif self._day_start_balance == 0.0:
            self._day_start_balance = balance

    def calculate_bet(self, balance: float) -> float:
        """Return a safe bet amount given the current balance."""
        bet = balance * self.balance_pct
        return round(max(self.min_bet, min(self.max_bet, bet)), 2)

    def can_trade(self, balance: float) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        today = date.today()
        if today != self._tracking_date:
            self._tracking_date = today
            self._day_start_balance = balance

        # -- daily trade count --
        today_trades = [t for t in self.trades if t.timestamp.date() == today]
        if len(today_trades) >= self.daily_trade_limit:
            return False, f"Daily trade limit reached ({self.daily_trade_limit})"

        # -- daily loss --
        daily_pnl = sum(
            t.profit for t in today_trades if t.profit is not None
        )
        if daily_pnl <= -self.max_daily_loss:
            return False, f"Daily loss limit reached (${-daily_pnl:.2f} lost)"

        # -- consecutive losses --
        cons = self._consecutive_losses()
        if cons >= self.max_consecutive_losses:
            return False, f"{cons} consecutive losses – cooling down"

        return True, "OK"

    def record_open(self, active: str, action: str, amount: float, duration: int) -> TradeRecord:
        rec = TradeRecord(
            timestamp=datetime.now(),
            active=active,
            action=action,
            amount=amount,
            duration=duration,
        )
        self.trades.append(rec)
        return rec

    def record_close(self, record: TradeRecord, profit: float):
        record.profit = profit
        record.win = profit > 0

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def total_trades(self) -> int:
        return len([t for t in self.trades if t.win is not None])

    @property
    def wins(self) -> int:
        return len([t for t in self.trades if t.win is True])

    @property
    def losses(self) -> int:
        return len([t for t in self.trades if t.win is False])

    @property
    def win_rate(self) -> float:
        total = self.total_trades
        return (self.wins / total * 100) if total > 0 else 0.0

    @property
    def total_pnl(self) -> float:
        return sum(t.profit for t in self.trades if t.profit is not None)

    @property
    def daily_pnl(self) -> float:
        today = date.today()
        return sum(
            t.profit for t in self.trades
            if t.profit is not None and t.timestamp.date() == today
        )

    @property
    def daily_trades_count(self) -> int:
        today = date.today()
        return len([t for t in self.trades if t.timestamp.date() == today])

    def _consecutive_losses(self) -> int:
        count = 0
        for t in reversed(self.trades):
            if t.win is None:
                continue
            if t.win is False:
                count += 1
            else:
                break
        return count

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses()

    def summary(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "total_pnl": round(self.total_pnl, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_trades": self.daily_trades_count,
            "consecutive_losses": self.consecutive_losses,
        }
