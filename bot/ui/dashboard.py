"""
Professional terminal dashboard built with `rich`.
All rendering is done through a single Live context updated periodically.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich import box

logger = logging.getLogger(__name__)

# ─── colour palette ─────────────────────────────────────────────────────────
C_TITLE   = "bold cyan"
C_WIN     = "bold green"
C_LOSS    = "bold red"
C_NEUTRAL = "bold yellow"
C_INFO    = "dim white"
C_HEADER  = "bold white on dark_blue"
C_ACCENT  = "bright_cyan"
C_WAIT    = "yellow"

LOGO = r"""
[bold cyan]
  ██╗ ██████╗     ██████╗  ██████╗ ████████╗
  ██║██╔═══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝
  ██║██║   ██║    ██████╔╝██║   ██║   ██║   
  ██║██║▄▄ ██║    ██╔══██╗██║   ██║   ██║   
  ██║╚██████╔╝    ██████╔╝╚██████╔╝   ██║   
  ╚═╝ ╚══▀▀═╝     ╚═════╝  ╚═════╝   ╚═╝   
[/bold cyan][dim]  Professional Automated Trading System v2.0[/dim]
"""


class Dashboard:
    """Manages the Rich live terminal UI."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._live: Optional[Live] = None

        # State updated by the bot
        self.balance: float = 0.0
        self.balance_mode: str = "PRACTICE"
        self.active_symbol: str = "—"
        self.active_asset: str = "—"
        self.signal_action: str = "WAIT"
        self.signal_conf: float = 0.0
        self.signal_reason: str = ""
        self.agent_signals: List[dict] = []
        self.trade_log: List[dict] = []        # recent trades (last 20)
        self.stats: dict = {}
        self.money_manager_info: str = ""
        self.bot_status: str = "Starting…"
        self.current_candle_close: float = 0.0
        self.allowed_to_trade: bool = True
        self.block_reason: str = ""

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        self._live = Live(
            self._build_layout(),
            console=self.console,
            refresh_per_second=2,
            screen=True,
        )
        self._live.__enter__()

    def stop(self):
        if self._live:
            self._live.__exit__(None, None, None)

    def refresh(self):
        if self._live:
            self._live.update(self._build_layout())

    # ── Layout builder ───────────────────────────────────────────────────────

    def _build_layout(self) -> Layout:
        root = Layout(name="root")
        root.split_column(
            Layout(name="header", size=9),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        root["header"].update(self._header_panel())
        root["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=3),
        )
        root["body"]["left"].split_column(
            Layout(name="account", size=11),
            Layout(name="agents"),
        )
        root["body"]["right"].split_column(
            Layout(name="signal", size=11),
            Layout(name="trades"),
        )
        root["body"]["left"]["account"].update(self._account_panel())
        root["body"]["left"]["agents"].update(self._agents_panel())
        root["body"]["right"]["signal"].update(self._signal_panel())
        root["body"]["right"]["trades"].update(self._trades_panel())
        root["footer"].update(self._footer_panel())
        return root

    # ── Individual panels ────────────────────────────────────────────────────

    def _header_panel(self) -> Panel:
        ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        status_style = C_WIN if self.bot_status == "Running" else C_NEUTRAL
        header_text = Text.from_markup(LOGO)
        header_text.append(f"\n  Status: ", style="dim white")
        header_text.append(f"{self.bot_status}", style=status_style)
        header_text.append(f"   ·   {ts}", style=C_INFO)
        return Panel(header_text, style="bold cyan", box=box.DOUBLE_EDGE)

    def _account_panel(self) -> Panel:
        mode_style = C_WIN if self.balance_mode == "PRACTICE" else C_ACCENT
        daily_pnl = self.stats.get("daily_pnl", 0.0)
        pnl_style = C_WIN if daily_pnl >= 0 else C_LOSS
        wr = self.stats.get("win_rate", 0.0)
        wr_style = C_WIN if wr >= 55 else (C_NEUTRAL if wr >= 45 else C_LOSS)

        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim white", justify="right")
        t.add_column(style="bold white")
        t.add_row("Account:", f"[{mode_style}]{self.balance_mode}[/{mode_style}]")
        t.add_row("Balance:", f"[bold white]${self.balance:,.2f}[/bold white]")
        t.add_row("Daily P&L:", f"[{pnl_style}]${daily_pnl:+.2f}[/{pnl_style}]")
        t.add_row("Total P&L:", f"[bold]${self.stats.get('total_pnl', 0.0):+.2f}[/bold]")
        t.add_row("Win Rate:", f"[{wr_style}]{wr:.1f}%[/{wr_style}]")
        t.add_row("Trades:", f"{self.stats.get('total_trades', 0):,}  "
                             f"([green]W:{self.stats.get('wins', 0)}[/green] "
                             f"[red]L:{self.stats.get('losses', 0)}[/red])")
        t.add_row("Strategy:", f"[dim cyan]{self.money_manager_info or '—'}[/dim cyan]")

        trade_ok = self.allowed_to_trade
        block_txt = f" – {self.block_reason}" if self.block_reason else ""
        t.add_row("Trading:", f"[{C_WIN if trade_ok else C_LOSS}]"
                              f"{'ENABLED' if trade_ok else 'BLOCKED' + block_txt}"
                              f"[/{C_WIN if trade_ok else C_LOSS}]")

        return Panel(t, title="[bold cyan]⬤ Account[/bold cyan]", box=box.ROUNDED)

    def _agents_panel(self) -> Panel:
        tbl = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style=C_HEADER,
                    expand=True, pad_edge=False)
        tbl.add_column("Agent", style="dim cyan", no_wrap=True)
        tbl.add_column("Signal", justify="center")
        tbl.add_column("Conf", justify="right")
        tbl.add_column("Reason", style="dim white", overflow="fold")

        for s in self.agent_signals:
            action = s.get("action", "wait").upper()
            conf = s.get("confidence", 0.0)
            if action == "CALL":
                action_txt = Text(f"▲ {action}", style=C_WIN)
            elif action == "PUT":
                action_txt = Text(f"▼ {action}", style=C_LOSS)
            else:
                action_txt = Text(f"● {action}", style=C_WAIT)
            conf_txt = Text(f"{conf*100:.0f}%",
                            style=C_WIN if conf >= 0.70 else (C_NEUTRAL if conf >= 0.50 else C_INFO))
            tbl.add_row(
                s.get("agent", ""),
                action_txt,
                conf_txt,
                s.get("reason", ""),
            )

        if not self.agent_signals:
            tbl.add_row("—", "—", "—", "Waiting for data…")

        return Panel(tbl, title="[bold cyan]⬤ Agent Signals[/bold cyan]", box=box.ROUNDED)

    def _signal_panel(self) -> Panel:
        action = self.signal_action
        conf = self.signal_conf

        if action == "CALL":
            action_txt = Text(f"▲  BUY CALL", style="bold green on dark_green")
            bar_style = "green"
        elif action == "PUT":
            action_txt = Text(f"▼  BUY PUT", style="bold red on dark_red")
            bar_style = "red"
        else:
            action_txt = Text(f"●  WAITING", style="bold yellow")
            bar_style = "yellow"

        t = Table.grid(padding=(0, 1))
        t.add_column(style="dim white", justify="right", width=12)
        t.add_column()
        t.add_row("Decision:", action_txt)
        t.add_row("Confidence:", self._conf_bar(conf, bar_style))
        t.add_row("Asset:", f"[bold]{self.active_symbol}[/bold]")
        t.add_row("Price:", f"[bright_white]{self.current_candle_close:.5f}[/bright_white]")
        t.add_row("Reason:", f"[dim]{self.signal_reason[:80]}[/dim]")

        return Panel(t, title="[bold cyan]⬤ Current Signal[/bold cyan]", box=box.ROUNDED)

    def _trades_panel(self) -> Panel:
        tbl = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style=C_HEADER,
                    expand=True, pad_edge=False)
        tbl.add_column("Time", style="dim white", width=8)
        tbl.add_column("Asset", width=10)
        tbl.add_column("Dir", justify="center", width=5)
        tbl.add_column("Bet", justify="right", width=8)
        tbl.add_column("Result", justify="right", width=10)
        tbl.add_column("P&L", justify="right", width=9)

        for t in reversed(self.trade_log[-20:]):
            ts = t.get("time", "")
            action = t.get("action", "")
            profit = t.get("profit")

            if action == "call":
                dir_txt = Text("▲", style=C_WIN)
            elif action == "put":
                dir_txt = Text("▼", style=C_LOSS)
            else:
                dir_txt = Text("?", style=C_INFO)

            if profit is None:
                result_txt = Text("open…", style=C_WAIT)
                pnl_txt = Text("—", style=C_INFO)
            elif profit > 0:
                result_txt = Text("WIN", style=C_WIN)
                pnl_txt = Text(f"+${profit:.2f}", style=C_WIN)
            else:
                result_txt = Text("LOSS", style=C_LOSS)
                pnl_txt = Text(f"-${abs(profit):.2f}", style=C_LOSS)

            tbl.add_row(
                ts,
                t.get("asset", ""),
                dir_txt,
                f"${t.get('amount', 0):.2f}",
                result_txt,
                pnl_txt,
            )

        if not self.trade_log:
            tbl.add_row("—", "—", "—", "—", "No trades yet", "—")

        return Panel(tbl, title="[bold cyan]⬤ Trade Log[/bold cyan]", box=box.ROUNDED)

    def _footer_panel(self) -> Panel:
        cons = self.stats.get("consecutive_losses", 0)
        max_cons = self.stats.get("max_consecutive_losses", 5)
        daily = self.stats.get("daily_trades", 0)
        daily_limit = self.stats.get("daily_trade_limit", 50)

        parts = [
            f"[dim]Consec. losses:[/dim] [{'red' if cons >= 3 else 'white'}]{cons}/{max_cons}[/]",
            f"[dim]Daily trades:[/dim] [white]{daily}/{daily_limit}[/]",
            f"[dim]Press Ctrl+C to stop[/dim]",
        ]
        return Panel(
            Text.from_markup("   ·   ".join(parts)),
            style="dim",
            box=box.HORIZONTALS,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _conf_bar(value: float, style: str = "cyan", width: int = 20) -> Text:
        filled = int(value * width)
        bar = "█" * filled + "░" * (width - filled)
        t = Text()
        t.append(bar, style=style)
        t.append(f" {value*100:.1f}%", style="bold white")
        return t

    # ── Update helpers (called by the bot) ───────────────────────────────────

    def update_signal(self, action: str, confidence: float, reason: str):
        self.signal_action = action.upper()
        self.signal_conf = confidence
        self.signal_reason = reason

    def update_agent_signals(self, signals: list):
        """signals: list of dicts with keys agent, action, confidence, reason"""
        self.agent_signals = signals

    def add_trade(self, trade: dict):
        self.trade_log.append(trade)

    def update_trade_result(self, index: int, profit: float):
        if 0 <= index < len(self.trade_log):
            self.trade_log[index]["profit"] = profit

    def update_stats(self, stats: dict):
        self.stats = stats

    def print_message(self, msg: str, style: str = ""):
        """Print a message below the live display (only visible after stop)."""
        if self._live:
            self._live.console.print(msg, style=style)
