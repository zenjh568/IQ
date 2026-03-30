"""
Main bot entry point.

Usage:
    python -m bot.main                        # uses config.json
    python -m bot.main --config myconfig.json
    python -m bot.main --generate-config      # write sample config.json and exit
    IQ_EMAIL=x IQ_PASSWORD=y python -m bot.main
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Logging must be configured before any module imports that use logging
# ---------------------------------------------------------------------------
LOG_FILE = Path("bot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
import bot.config as config_module
from bot.agents.base_agent import Signal
from bot.agents.bollinger_agent import BollingerAgent
from bot.agents.macd_agent import MACDAgent
from bot.agents.multi_confirmation_agent import MultiConfirmationAgent
from bot.agents.rsi_agent import RSIAgent
from bot.agents.stochastic_agent import StochasticAgent
from bot.strategies.money_manager import MoneyManager
from bot.strategies.risk_manager import RiskManager
from bot.strategies.signal_filter import SignalFilter
from bot.ui.dashboard import Dashboard
from bot.ui.login import prompt_credentials
from bot.utils.indicators import candles_to_ohlc

# ---------------------------------------------------------------------------


class TradingBot:
    """Orchestrates agents, risk management, and trade execution."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.api = None
        self.dashboard = Dashboard()
        self.risk_manager = RiskManager(cfg["risk_management"])
        self.money_manager = MoneyManager(cfg["money_management"])
        self.signal_filter = SignalFilter(cfg["signal_filter"])
        self.agents = self._build_agents()
        self._running = False
        self._open_trades: Dict[int, dict] = {}   # order_id → trade info

    # ── Agent factory ────────────────────────────────────────────────────────

    def _build_agents(self):
        ac = self.cfg["agents"]
        return [
            RSIAgent(ac["rsi"]),
            MACDAgent(ac["macd"]),
            BollingerAgent(ac["bollinger"]),
            StochasticAgent(ac["stochastic"]),
            MultiConfirmationAgent(ac["multi_confirmation"]),
        ]

    # ── Connection ───────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to IQ Option API."""
        try:
            # Import here so the module can be tested without the API zip
            sys.path.insert(0, str(Path(__file__).parent.parent / "iqoptionapi-master"))
            from iqoptionapi.stable_api import IQ_Option  # type: ignore

            self.dashboard.bot_status = "Connecting…"
            self.dashboard.refresh()

            self.api = IQ_Option(self.cfg["email"], self.cfg["password"])
            connected, reason = self.api.connect()
            if not connected:
                logger.error("Connection failed: %s", reason)
                return False

            # Switch account type
            self.api.change_balance(self.cfg["account_type"])
            logger.info("Connected to IQ Option (%s)", self.cfg["account_type"])
            return True
        except Exception as exc:
            logger.exception("connect() error: %s", exc)
            return False

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        self.dashboard.start()
        self.dashboard.bot_status = "Running"

        try:
            if not self.connect():
                self.dashboard.bot_status = "Connection failed – check bot.log"
                self.dashboard.refresh()
                time.sleep(5)
                return

            assets: List[str] = self.cfg["assets"]
            asset_idx = 0

            while self._running:
                asset = assets[asset_idx % len(assets)]
                asset_idx += 1

                try:
                    self._cycle(asset)
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    logger.exception("Cycle error for %s: %s", asset, exc)
                    self.dashboard.bot_status = f"Error: {exc}"

                self.dashboard.refresh()
                time.sleep(self.cfg.get("loop_interval", 5))

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            self._running = False
            self.dashboard.bot_status = "Stopped"
            self.dashboard.refresh()
            time.sleep(0.5)
            self.dashboard.stop()

    # ── Single analysis + trade cycle ────────────────────────────────────────

    def _cycle(self, asset: str):
        # ── 1. Fetch balance ─────────────────────────────────────────────────
        balance = self.api.get_balance()
        self.dashboard.balance = balance
        self.dashboard.balance_mode = self.cfg["account_type"]
        self.risk_manager.set_balance(balance)

        # ── 2. Risk gate ─────────────────────────────────────────────────────
        allowed, reason = self.risk_manager.can_trade(balance)
        self.dashboard.allowed_to_trade = allowed
        self.dashboard.block_reason = "" if allowed else reason

        # ── 3. Fetch candles ─────────────────────────────────────────────────
        candle_size = self.cfg.get("candle_size", 60)
        count = self.cfg.get("candle_count", 100)
        end_time = time.time()
        candles = self.api.get_candles(asset, candle_size, count, end_time)

        if not candles or len(candles) < 30:
            self.dashboard.update_signal("WAIT", 0.0, f"Not enough candles for {asset}")
            self.dashboard.active_symbol = asset
            self._update_dashboard_stats()
            return

        opens, highs, lows, closes = candles_to_ohlc(candles)
        self.dashboard.current_candle_close = closes[-1] if closes else 0.0
        self.dashboard.active_symbol = asset

        # ── 4. Run agents ─────────────────────────────────────────────────────
        raw_signals: List[Signal] = []
        agent_ui: List[dict] = []

        for agent in self.agents:
            sig = agent.get_signal(opens, highs, lows, closes)
            raw_signals.append(sig)
            agent_ui.append({
                "agent": agent.name,
                "action": sig.action,
                "confidence": sig.confidence,
                "reason": sig.reason,
            })

        self.dashboard.update_agent_signals(agent_ui)

        # ── 5. Filter signals ─────────────────────────────────────────────────
        final: Optional[Signal] = self.signal_filter.filter(raw_signals)

        if final is None:
            self.dashboard.update_signal("WAIT", 0.0, "No consensus signal")
            self._update_dashboard_stats()
            return

        self.dashboard.update_signal(final.action.upper(), final.confidence, final.reason)

        if not allowed:
            logger.info("Signal %s for %s ignored – risk gate: %s", final.action, asset, reason)
            self._update_dashboard_stats()
            return

        # ── 6. Human-like hesitation before placing the trade ────────────────
        # Simulate the variable reaction time a real trader would have.
        hb = self.cfg.get("human_behavior", {})
        think_time = random.uniform(
            hb.get("think_min", 1.5),
            hb.get("think_max", 4.5),
        )
        self.dashboard.bot_status = f"Analisando sinal ({think_time:.1f}s)…"
        self.dashboard.refresh()
        time.sleep(think_time)

        # Occasionally skip a borderline signal (human-like caution).
        # Threshold and probability are configurable via config["human_behavior"].
        hb = self.cfg.get("human_behavior", {})
        skip_conf_threshold = hb.get("skip_conf_threshold", 0.75)
        skip_probability = hb.get("skip_probability", 0.08)
        if final.confidence < skip_conf_threshold and random.random() < skip_probability:
            logger.info("Signal skipped (human-like caution): conf=%.2f", final.confidence)
            self.dashboard.update_signal("WAIT", 0.0, "Sinal ignorado por cautela")
            self._update_dashboard_stats()
            return

        # ── 7. Place trade ────────────────────────────────────────────────────
        bet = self.money_manager.next_bet(
            balance,
            self.cfg["risk_management"]["min_bet"],
            self.cfg["risk_management"]["max_bet"],
            confidence=final.confidence,
        )
        self.dashboard.money_manager_info = self.money_manager.strategy_info

        duration = self.cfg.get("duration", 1)
        logger.info("Placing %s on %s  bet=$%.2f  conf=%.2f  reason=%s",
                    final.action, asset, bet, final.confidence, final.reason)

        trade_record = self.risk_manager.record_open(asset, final.action, bet, duration)

        # Log to dashboard immediately (result TBD)
        trade_ui = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "asset": asset,
            "action": final.action,
            "amount": bet,
            "profit": None,
        }
        trade_idx = len(self.dashboard.trade_log)
        self.dashboard.add_trade(trade_ui)
        self.dashboard.refresh()

        # Place the actual option
        try:
            status, order_id = self.api.buy(bet, asset, final.action, duration)
            if not status:
                logger.warning("Buy rejected for %s", asset)
                self.dashboard.trade_log[trade_idx]["profit"] = 0.0
                self._update_dashboard_stats()
                return

            self._open_trades[order_id] = {
                "trade_record": trade_record,
                "trade_idx": trade_idx,
                "bet": bet,
                "asset": asset,
                "action": final.action,
            }

            # Wait for result (blocking in this simple implementation)
            profit = self._wait_for_result(order_id, duration * 60 + 10)
            self._handle_result(order_id, profit)

        except Exception as exc:
            logger.exception("Trade execution error: %s", exc)

        self._update_dashboard_stats()

    # ── Result handling ───────────────────────────────────────────────────────

    def _wait_for_result(self, order_id: int, timeout: int) -> float:
        """Poll for the trade result.  Returns profit (negative if loss)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = self.api.check_win_v3(order_id)
                if result is not None:
                    return result
            except Exception:
                pass
            self.dashboard.bot_status = f"Waiting for result (#{order_id})…"
            self.dashboard.refresh()
            time.sleep(1)
        logger.warning("Timeout waiting for result of order %d", order_id)
        return 0.0

    def _handle_result(self, order_id: int, profit: float):
        info = self._open_trades.pop(order_id, None)
        if not info:
            return

        won = profit > 0
        self.risk_manager.record_close(info["trade_record"], profit)
        self.money_manager.record_result(won, profit)

        # Update dashboard trade row
        idx = info["trade_idx"]
        self.dashboard.update_trade_result(idx, profit)

        logger.info("Trade result: %s $%.2f  profit=$%.2f  won=%s",
                    info["asset"], info["bet"], profit, won)
        self.dashboard.bot_status = "Running"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_dashboard_stats(self):
        stats = self.risk_manager.summary()
        stats["max_consecutive_losses"] = self.risk_manager.max_consecutive_losses
        stats["daily_trade_limit"] = self.risk_manager.daily_trade_limit
        self.dashboard.update_stats(stats)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="IQ Option Professional Trading Bot")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--generate-config", action="store_true",
                        help="Write a sample config.json and exit")
    args = parser.parse_args()

    if args.generate_config:
        config_module.save_sample(args.config)
        sys.exit(0)

    cfg = config_module.load(args.config)

    # Show interactive login form if credentials are not already configured
    if not cfg["email"] or not cfg["password"]:
        cfg = prompt_credentials(cfg, config_path=args.config)

    if not cfg["email"] or not cfg["password"]:
        print(
            "\n[ERROR] Credenciais não fornecidas.\n"
            "  Opção 1: Preencha os campos no formulário de login\n"
            "  Opção 2: Edite config.json (campos email + password)\n"
            "  Opção 3: Defina IQ_EMAIL e IQ_PASSWORD como variáveis de ambiente\n"
        )
        sys.exit(1)

    bot = TradingBot(cfg)
    bot.run()


if __name__ == "__main__":
    main()
