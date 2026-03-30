"""
Configuration management.

Priority (highest to lowest):
  1. Environment variables  IQ_EMAIL, IQ_PASSWORD, IQ_ACCOUNT_TYPE
  2. config.json in working directory
  3. Built-in defaults

Run `python -m bot.config` to generate a sample config.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    # ── Credentials ──────────────────────────────────────────────────────────
    "email": "",
    "password": "",
    "account_type": "PRACTICE",   # PRACTICE | REAL

    # ── Asset / timing ───────────────────────────────────────────────────────
    "assets": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
    "duration": 1,                 # option duration in minutes
    "candle_size": 60,             # candle size in seconds (60 = 1 min)
    "candle_count": 100,           # how many historical candles to fetch

    # ── Signal filter ─────────────────────────────────────────────────────────
    "signal_filter": {
        "mode": "weighted",        # majority | unanimous | weighted | best
        "confidence_threshold": 0.68,
        "agent_weights": {
            "Multi-Confirmation Agent": 3.0,
            "RSI Agent": 1.0,
            "MACD Agent": 1.0,
            "Bollinger Bands Agent": 1.0,
            "Stochastic Agent": 1.0,
        },
    },

    # ── Agents ────────────────────────────────────────────────────────────────
    "agents": {
        "rsi": {
            "enabled": True,
            "period": 14,
            "oversold": 28,
            "overbought": 72,
            "ema_confirm": True,
            "min_confidence": 0.62,
        },
        "macd": {
            "enabled": True,
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "rsi_filter": True,
            "min_confidence": 0.62,
        },
        "bollinger": {
            "enabled": True,
            "period": 20,
            "std_dev": 2.0,
            "atr_min": 0.0008,
            "min_confidence": 0.62,
        },
        "stochastic": {
            "enabled": True,
            "k_period": 14,
            "d_period": 3,
            "oversold": 20,
            "overbought": 80,
            "min_confidence": 0.62,
        },
        "multi_confirmation": {
            "enabled": True,
            "min_confirmations": 4,
            "min_confidence": 0.68,
        },
    },

    # ── Money management ──────────────────────────────────────────────────────
    "money_management": {
        "strategy": "flat",        # flat | martingale | anti_martingale | soros | fibonacci
        "base_bet": 1.0,
        "martingale_max": 4,
        "soros_cycles": 3,
        "max_bet": 50.0,
        "min_bet": 1.0,
        "confidence_scaling": True,   # scale bet up to 1.5x on high-confidence signals
    },

    # ── Risk management ───────────────────────────────────────────────────────
    "risk_management": {
        "max_daily_loss": 30.0,
        "max_consecutive_losses": 5,
        "balance_pct_per_trade": 0.02,
        "min_bet": 1.0,
        "max_bet": 50.0,
        "daily_trade_limit": 40,
    },

    # ── Loop timing ───────────────────────────────────────────────────────────
    "loop_interval": 5,            # seconds between analysis cycles

    # ── Human-like behaviour ─────────────────────────────────────────────────
    # think_min / think_max: random hesitation (seconds) before each trade.
    # skip_conf_threshold: skip signals below this confidence with skip_probability.
    # skip_probability: fraction [0,1] of borderline signals to pass on.
    "human_behavior": {
        "think_min": 1.5,
        "think_max": 4.5,
        "skip_conf_threshold": 0.75,
        "skip_probability": 0.08,
    },
}


def load(path: str = "config.json") -> Dict[str, Any]:
    """Load config with env-var overrides."""
    cfg = dict(DEFAULT_CONFIG)

    # Load from file if it exists
    p = Path(path)
    if p.exists():
        with p.open() as f:
            file_cfg = json.load(f)
        _deep_merge(cfg, file_cfg)

    # Environment variable overrides
    if os.environ.get("IQ_EMAIL"):
        cfg["email"] = os.environ["IQ_EMAIL"]
    if os.environ.get("IQ_PASSWORD"):
        cfg["password"] = os.environ["IQ_PASSWORD"]
    if os.environ.get("IQ_ACCOUNT_TYPE"):
        cfg["account_type"] = os.environ["IQ_ACCOUNT_TYPE"]

    return cfg


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def save_sample(path: str = "config.json"):
    with open(path, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"Sample config written to {path}")


if __name__ == "__main__":
    save_sample(sys.argv[1] if len(sys.argv) > 1 else "config.json")
