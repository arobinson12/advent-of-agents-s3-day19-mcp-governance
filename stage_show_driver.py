#!/usr/bin/env python3
# ==============================================================================
# Advent of Agents Season 3 — Day 19 Theatrical Stage Show Driver
# Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints
# ==============================================================================
"""
High-impact 5-Command Simulated Typing Driver for YouTube/Keynote screen recording.

Commands:
  1. python3 registry_control_plane.py onboard-github
  2. python3 dynamic_mcp_agent.py
  3. python3 registry_control_plane.py cutover-v2
  4. python3 dynamic_mcp_agent.py
  5. python3 registry_control_plane.py revoke && python3 dynamic_mcp_agent.py
"""

import argparse
import os
import random
import subprocess
import sys
import time
from typing import Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(width=int(os.environ.get("COLUMNS", 110)))


def resolve_project_env():
    project_id = os.environ.get("PROJECT_ID")
    if not project_id:
        try:
            project_id = subprocess.check_output(
                ["gcloud", "config", "get-value", "project"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            project_id = "bu2-prod-data"
    region = os.environ.get("REGION", "us-central1")
    project_number = os.environ.get("PROJECT_NUMBER", "918024802560")
    return project_id, region, project_number


PROJECT_ID, REGION, PROJECT_NUMBER = resolve_project_env()
PROMPT_STRING = "\033[1;32mahmad@finserv-secops\033[0m:\033[1;34m~/advent-day19-demo\033[0m$ "


def read_single_key() -> str:
    """Read a single keypress from standard input in raw mode."""
    if not sys.stdin.isatty():
        return "\n"
    import termios
    import tty
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def print_hud(stage_title: str, step_desc: str, hud_state: Dict[str, str]):
    """Render persistent visual Governance Control Plane HUD panel on screen."""
    hud_table = Table.grid(expand=True)
    hud_table.add_column(style="bold yellow", width=22)
    hud_table.add_column(style="white", width=88)

    hud_table.add_row("Current Act:", f"[bold cyan]{stage_title}[/bold cyan] ➔ [white]{step_desc}[/white]")
    hud_table.add_row("Model Armor Floor:", f"[bold magenta]{hud_state.get('model_armor', 'GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK')}[/bold magenta]")
    hud_table.add_row("Active Tool Endpoint:", f"[cyan]{hud_state.get('physical_uri', 'https://github-mcp-v1-...run.app/mcp')}[/cyan]")
    hud_table.add_row("Outbound Binding:", f"{hud_state.get('binding_state', '[bold green]APPROVED & BOUND (secops-auditor ➔ github-mcp)[/bold green]')}")
    hud_table.add_row("Bound AuthProvider:", f"[green]{hud_state.get('auth_provider', 'github-auth [roles/agentidentity.user ✓]')}[/green]")

    console.print(Panel(
        hud_table,
        title="[bold white]ENTERPRISE GOVERNANCE CONTROL PLANE HUD[/bold white]",
        border_style="cyan",
        subtitle=f"[dim]Google Cloud Agent Registry (agentregistry.googleapis.com/mcp) | Region: {REGION}[/dim]"
    ))


def type_and_run(
    cmd: str,
    stage_title: str,
    step_num: int,
    step_desc: str,
    hud_state: Dict[str, str],
    mode: str = "auto"
):
    """
    Simulate human command typing with persistent HUD and clean stationary terminal positioning.
    Keeps terminal stationary at the top of the viewport so the presenter never has to scroll up.
    """
    if mode != "non-interactive":
        console.clear()

    print_hud(stage_title, f"Command {step_num}: {step_desc}", hud_state)
    sys.stdout.write(PROMPT_STRING)
    sys.stdout.flush()

    if mode == "non-interactive" or not sys.stdin.isatty():
        # Headless mode: print command cleanly and run
        sys.stdout.write(cmd + "\n")
        sys.stdout.flush()
        time.sleep(0.3)
    elif mode == "live-keys":
        # HackerTyper mode: each physical keypress types 2-3 characters
        cue = " \033[2m[Tap any keys to type, ENTER to run]\033[0m"
        sys.stdout.write(cue)
        sys.stdout.flush()

        idx = 0
        first_key = True
        while idx < len(cmd):
            ch = read_single_key()
            if first_key:
                # Erase cue
                sys.stdout.write("\r" + "\033[K" + PROMPT_STRING)
                sys.stdout.flush()
                first_key = False

            if ch in ("\r", "\n"):
                # Finish remaining command instantly
                sys.stdout.write(cmd[idx:])
                sys.stdout.flush()
                break
            else:
                chunk = cmd[idx:idx + 3]
                sys.stdout.write(chunk)
                sys.stdout.flush()
                idx += 3

        time.sleep(0.25)
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        # Default Auto-Type Mode: wait for ENTER or SPACE, then simulate human typing
        cue = " \033[2m[Press ENTER or SPACE to type & run]\033[0m"
        sys.stdout.write(cue)
        sys.stdout.flush()

        # Wait for key
        read_single_key()
        # Erase prompt line cue
        sys.stdout.write("\r" + "\033[K" + PROMPT_STRING)
        sys.stdout.flush()

        # Type character by character with slight natural jitter
        for c in cmd:
            sys.stdout.write(c)
            sys.stdout.flush()
            time.sleep(random.uniform(0.018, 0.035))

        time.sleep(0.25)
        sys.stdout.write("\n")
        sys.stdout.flush()

    # Execute the command
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0 and "revoke" not in cmd and "dynamic_mcp_agent.py" not in cmd:
        console.print(f"[bold red]Command exited with code {result.returncode}[/bold red]")
    console.print("")

    # Stationary review pause: allows presenter to speak to audience without screen scrolling away
    if mode != "non-interactive" and sys.stdin.isatty():
        sys.stdout.write(" \033[1;36m▶\033[0m \033[2m[Step complete. Press ENTER or SPACE to proceed to next command]\033[0m")
        sys.stdout.flush()
        read_single_key()


def run_stage_show(mode: str = "auto"):
    if mode != "non-interactive":
        console.clear()

    console.print(Panel(
        f"[bold cyan]ADVENT OF AGENTS SEASON 3 — DAY 19[/bold cyan]\n"
        f"[bold green]Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints[/bold green]\n"
        f"Use Case: [bold yellow]GitHub MCP + AuthProvider + Outbound Binding[/bold yellow]\n"
        f"Region: [bold yellow]{REGION}[/bold yellow] | Execution Mode: [bold magenta]{mode.upper()}[/bold magenta]",
        title="🎥 Studio Recording Stage Show (5 Punchy Commands)",
        border_style="green"
    ))

    if mode != "non-interactive" and sys.stdin.isatty():
        sys.stdout.write(" \033[1;36m▶\033[0m \033[2m[Press ENTER or SPACE to launch Command 1]\033[0m")
        sys.stdout.flush()
        read_single_key()

    github_v1_url = "https://github-mcp-v1-gcmp33r4ma-uc.a.run.app/mcp"
    github_v2_url = "https://github-mcp-v2-gcmp33r4ma-uc.a.run.app/mcp"

    hud_state = {
        "model_armor": "GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK (Active)",
        "physical_uri": github_v1_url,
        "binding_state": "[bold green]APPROVED & BOUND (secops-auditor ➔ github-mcp)[/bold green]",
        "auth_provider": "github-auth (Fine-Grained PAT / OAuth 3LO) [roles/agentidentity.user ✓]"
    }

    # ==========================================================================
    # Command 1: Onboard GitHub MCP + AuthProvider + Outbound Binding
    # ==========================================================================
    act1 = "Act 1: Onboard GitHub MCP + AuthProvider + Binding"
    type_and_run(
        "python3 registry_control_plane.py onboard-github",
        act1, 1, "Execute 3-Part Handshake & CQRS Ingestion",
        hud_state, mode
    )

    # ==========================================================================
    # Command 2: Dynamic Resolution & Bound-Auth Invocation of github-mcp-v1
    # ==========================================================================
    act2 = "Act 2: Governed Tool Resolution & Execution"
    type_and_run(
        "python3 dynamic_mcp_agent.py",
        act2, 2, "Dynamic Resolution & Bound-Auth Invocation of github-mcp-v1",
        hud_state, mode
    )

    # ==========================================================================
    # Command 3: Zero-Downtime Cutover from github-mcp-v1 to github-mcp-v2
    # ==========================================================================
    act3 = "Act 3: Zero-Downtime Tool Cutover"
    hud_state["physical_uri"] = github_v2_url
    type_and_run(
        "python3 registry_control_plane.py cutover-v2",
        act3, 3, "Migrate Physical URI to github-mcp-v2 with Zero Downtime",
        hud_state, mode
    )

    # ==========================================================================
    # Command 4: Re-Run Agent with Zero Code Changes against github-mcp-v2
    # ==========================================================================
    act3b = "Act 3: Post-Cutover Agent Verification"
    type_and_run(
        "python3 dynamic_mcp_agent.py",
        act3b, 4, "Re-Run Agent with Zero Code Changes against github-mcp-v2",
        hud_state, mode
    )

    # ==========================================================================
    # Command 5: Central Kill-Switch & Immediate Verification
    # ==========================================================================
    act4 = "Act 4: Central Kill-Switch & Policy Revocation"
    hud_state["physical_uri"] = "[dim]REVOKED / UNREGISTERED[/dim]"
    hud_state["binding_state"] = "[bold red]REVOKED & TERMINATED[/bold red]"
    hud_state["auth_provider"] = "[dim]DISCONNECTED[/dim]"
    type_and_run(
        "python3 registry_control_plane.py revoke && python3 dynamic_mcp_agent.py",
        act4, 5, "Trigger Emergency Kill-Switch & Verify Immediate Agent Block",
        hud_state, mode
    )

    # Stage Show Finale
    if mode != "non-interactive":
        console.clear()

    console.print(Panel(
        "[bold green]🎉 ADVENT OF AGENTS DAY 19 STAGE SHOW COMPLETE![/bold green]\n\n"
        "Key Governance Takeaways Demonstrated Live:\n"
        "  1. [bold cyan]3-Part Handshake:[/bold cyan] Governed 3P MCPs (GitHub/Figma) require Service + AuthProvider/IAM + Binding.\n"
        "  2. [bold cyan]Zero Secrets in Agent Code:[/bold cyan] Zero hardcoded URLs and zero GITHUB_TOKEN in agent code or .env.\n"
        "  3. [bold cyan]Zero-Downtime Cutover:[/bold cyan] Migrated from v1 to v2 without changing a single line of agent code.\n"
        "  4. [bold cyan]Instant Kill-Switch:[/bold cyan] Revoking the Outbound Binding instantly blocks rogue agent execution.\n"
        "  5. [bold cyan]Model Armor Guardrails:[/bold cyan] GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK prevents uninspected tool invocations.",
        title="🎬 Cut! Video Recording Complete",
        border_style="green"
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Advent of Agents Day 19 Stage Show Driver")
    parser.add_argument("--live-keys", action="store_true", help="HackerTyper mode: tap any keys to type")
    parser.add_argument("--non-interactive", action="store_true", help="Automated continuous run without pauses")
    args = parser.parse_args()

    mode = "auto"
    if args.live_keys:
        mode = "live-keys"
    elif args.non_interactive:
        mode = "non-interactive"

    run_stage_show(mode=mode)
