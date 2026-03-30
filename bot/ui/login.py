"""
Interactive login screen shown at startup when IQ Option credentials are missing.

Prompts the user for e-mail, password, and account type using a rich terminal UI.
The password is read with :func:`getpass.getpass` so it is never echoed.
"""
from __future__ import annotations

import getpass
import json
from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text

_LOGO = r"""
[bold cyan]
  ██╗ ██████╗     ██████╗  ██████╗ ████████╗
  ██║██╔═══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝
  ██║██║   ██║    ██████╔╝██║   ██║   ██║   
  ██║██║▄▄ ██║    ██╔══██╗██║   ██║   ██║   
  ██║╚██████╔╝    ██████╔╝╚██████╔╝   ██║   
  ╚═╝ ╚══▀▀═╝     ╚═════╝  ╚═════╝   ╚═╝   
[/bold cyan][dim]  Professional Automated Trading System v2.0[/dim]
"""


def prompt_credentials(cfg: Dict[str, Any], config_path: str = "config.json") -> Dict[str, Any]:
    """Show an interactive login form and return the updated config.

    Fields that are already filled in ``cfg`` are displayed (not re-asked).
    The user is offered the option to persist the credentials to
    ``config_path`` at the end.

    Parameters
    ----------
    cfg:
        Current configuration dict (may already contain partial credentials).
    config_path:
        Path to the JSON config file used for optional saving.

    Returns
    -------
    dict
        A copy of *cfg* with the credentials filled in.
    """
    console = Console()
    console.clear()
    console.print(Panel(Text.from_markup(_LOGO), style="bold cyan", border_style="bright_cyan"))
    console.print()
    console.print(
        Panel(
            "[bold white]Insira suas credenciais da IQ Option para continuar[/bold white]\n"
            "[dim]A senha nunca é armazenada em texto puro na memória durante a sessão[/dim]",
            title="[bold cyan]🔐  Login – IQ Option[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    email: str = cfg.get("email", "")
    password: str = cfg.get("password", "")
    account_type: str = cfg.get("account_type", "PRACTICE")

    # ── Email ────────────────────────────────────────────────────────────────
    if email:
        console.print(f"  [dim white]📧 Email:[/dim white] [cyan]{email}[/cyan]  [dim](já configurado)[/dim]")
    else:
        email = Prompt.ask("  [bold cyan]📧 Email[/bold cyan]", console=console).strip()

    # ── Password ─────────────────────────────────────────────────────────────
    if password:
        console.print("  [dim white]🔑 Senha:[/dim white] [dim]••••••••  (já configurada)[/dim]")
    else:
        console.print()
        password = getpass.getpass("  🔑 Senha (oculta): ").strip()

    # ── Account type ─────────────────────────────────────────────────────────
    console.print()
    account_type = Prompt.ask(
        "  [bold cyan]💼 Tipo de conta[/bold cyan]",
        choices=["PRACTICE", "REAL"],
        default=account_type,
        console=console,
    )

    # ── Save option ──────────────────────────────────────────────────────────
    console.print()
    save = Confirm.ask(
        "  [bold yellow]💾 Salvar credenciais em config.json?[/bold yellow]",
        default=False,
        console=console,
    )

    cfg = dict(cfg)
    cfg["email"] = email
    cfg["password"] = password
    cfg["account_type"] = account_type

    if save:
        try:
            with open(config_path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, indent=2, ensure_ascii=False)
            console.print(f"\n  [bold green]✔  Configurações salvas em {config_path}[/bold green]")
        except OSError as exc:
            console.print(f"\n  [red]✗  Não foi possível salvar: {exc}[/red]")

    console.print()
    return cfg
