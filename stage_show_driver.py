#!/usr/bin/env python3
"""
Advent of Agents Season 3 — Day 19 Theatrical Stage Show Driver
Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints

Implements:
1. Simulated human typing (`type_and_run`) with 3 modes:
   - Default: Auto-types on [ENTER] / [SPACE]
   - --live-keys: HackerTyper live keystroke mode
   - --non-interactive: Headless verification mode
2. Persistent high-contrast Governance Control Plane HUD on screen between beats.
3. The 4 Acts and 10 Auto-Typed Commands executed end-to-end.
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

    hud_table.add_row("Current Stage:", f"[bold cyan]{stage_title}[/bold cyan] ➔ [white]{step_desc}[/white]")
    hud_table.add_row("Model Armor Floor:", f"[bold magenta]{hud_state.get('model_armor', 'GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK')}[/bold magenta]")
    hud_table.add_row("Active Tool Endpoint:", f"[cyan]{hud_state.get('physical_uri', 'https://finserv-ledger-mcp-v1-.../mcp')}[/cyan]")
    hud_table.add_row("Outbound Binding:", f"{hud_state.get('binding_state', '[bold green]APPROVED & BOUND (finserv-auditor ➔ finserv-ledger)[/bold green]')}")

    console.print(Panel(
        hud_table,
        title="[bold white]ENTERPRISE GOVERNANCE CONTROL PLANE HUD[/bold white]",
        border_style="cyan",
        subtitle="[dim]Google Cloud Agent Registry (agentregistry.googleapis.com/mcp) | Region: us-central1[/dim]"
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
    Simulate human command typing with persistent HUD and clean terminal positioning.
    Keeps terminal stationary at the top of the viewport so the presenter never has to scroll up.
    """
    if mode != "non-interactive":
        console.clear()

    print_hud(stage_title, f"Step {step_num}: {step_desc}", hud_state)
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
        ch = read_single_key()
        # Erase prompt line cue
        sys.stdout.write("\r" + "\033[K" + PROMPT_STRING)
        sys.stdout.flush()

        # Type character by character with slight natural jitter
        for c in cmd:
            sys.stdout.write(c)
            sys.stdout.flush()
            time.sleep(random.uniform(0.020, 0.038))

        time.sleep(0.30)
        sys.stdout.write("\n")
        sys.stdout.flush()

    # Execute the command
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0 and "dynamic_mcp_agent.py" not in cmd:
        console.print(f"[bold red]Command exited with code {result.returncode}[/bold red]")
    console.print("")

    # Stationary review pause: allows presenter to speak to audience without screen scrolling away
    if mode != "non-interactive" and sys.stdin.isatty():
        sys.stdout.write(" \033[1;36m▶\033[0m \033[2m[Step complete. Press ENTER or SPACE to proceed to next stage]\033[0m")
        sys.stdout.flush()
        read_single_key()


def run_stage_show(mode: str = "auto"):
    if mode != "non-interactive":
        console.clear()

    console.print(Panel(
        f"[bold cyan]ADVENT OF AGENTS SEASON 3 — DAY 19[/bold cyan]\n"
        f"[bold green]Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints[/bold green]\n"
        f"Environment: [bold yellow]Enterprise Production[/bold yellow] | Region: [bold yellow]{REGION}[/bold yellow]\n"
        f"Execution Mode: [bold magenta]{mode.upper()}[/bold magenta] (Options: default auto-type, --live-keys, --non-interactive)",
        title="🎥 Studio Recording Stage Show",
        border_style="green"
    ))

    if mode != "non-interactive" and sys.stdin.isatty():
        sys.stdout.write(" \033[1;36m▶\033[0m \033[2m[Press ENTER or SPACE to launch Stage 1]\033[0m")
        sys.stdout.flush()
        read_single_key()

    # Initial Ready HUD State
    ledger_v1_url = f"https://finserv-ledger-mcp-v1-{PROJECT_NUMBER}.{REGION}.run.app/mcp"
    ledger_v2_url = f"https://finserv-ledger-mcp-v2-{PROJECT_NUMBER}.{REGION}.run.app/mcp"
    canonical_mcp_urn = f"urn:mcp:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:finserv-ledger-mcp"

    hud_state = {
        "model_armor": "GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK (Global Perimeter Active)",
        "logical_urn": canonical_mcp_urn,
        "physical_uri": ledger_v1_url,
        "binding_state": "[bold green]APPROVED & BOUND (finserv-auditor ➔ finserv-ledger)[/bold green]"
    }

    # ==========================================================================
    # Stage 1: The Problem & Scale Architecture (Commands 1-4)
    # ==========================================================================
    stage1 = "Stage 1: The Problem & Scale Ingestion Architecture"
    type_and_run(
        "python3 registry_control_plane.py show-agent-code",
        stage1, 1, "Inspect Agent Runtime Architecture: Eliminating Hardcoded MCP URLs",
        hud_state, mode
    )

    type_and_run(
        "python3 registry_control_plane.py show-onboarding-specs",
        stage1, 2, "Examine the 3 Onboarding Pipelines (Auto-Ingest, ToolSpec, Terraform IaC)",
        hud_state, mode
    )

    type_and_run(
        "python3 registry_control_plane.py list-meta-tools",
        stage1, 3, "Enumerate 20 Built-in Governance Meta-Tools on Agent Registry Remote MCP",
        hud_state, mode
    )

    type_and_run(
        "python3 registry_control_plane.py onboard-all",
        stage1, 4, "Onboard All 3 Service Types (MCP, Agent, REST) & Outbound Binding",
        hud_state, mode
    )

    # ==========================================================================
    # Stage 2: Zero-Hardcoded-URL Autonomous Execution (Commands 5-6)
    # ==========================================================================
    stage2 = "Stage 2: Zero-Hardcoded-URL Autonomous Execution"
    type_and_run(
        "python3 registry_control_plane.py inspect-catalog",
        stage2, 5, "Inspect CQRS Projection Table (Writable Services ➔ Read-Only Catalog)",
        hud_state, mode
    )

    type_and_run(
        "python3 dynamic_mcp_agent.py",
        stage2, 6, "Execute Governed ADK Agent (Runtime Resolution via Gemini 3.8 Flash)",
        hud_state, mode
    )

    # ==========================================================================
    # Stage 3: Zero-Downtime Governance Cutover (Commands 7-8)
    # ==========================================================================
    stage3 = "Stage 3: Zero-Downtime Governance Cutover (v1 ➔ v2)"
    hud_state["physical_uri"] = f"[bold green]{ledger_v2_url} (v2 Post-Quantum Hardened)[/bold green]"
    type_and_run(
        "python3 registry_control_plane.py cutover-v2",
        stage3, 7, "Promote v2 Hardened Endpoint (Logical URN & Outbound Binding Invariance)",
        hud_state, mode
    )

    type_and_run(
        "python3 dynamic_mcp_agent.py",
        stage3, 8, "Execute Same Agent Without Any Code Modifications (Seamless v2 Routing)",
        hud_state, mode
    )

    # ==========================================================================
    # Stage 4: Emergency Revocation & Model Armor Kill Switch (Commands 9-11)
    # ==========================================================================
    stage4 = "Stage 4: Emergency Revocation & Model Armor Kill Switch"
    hud_state["binding_state"] = "[bold red]REVOKED / QUARANTINED (KILL SWITCH ENFORCED)[/bold red]"
    hud_state["physical_uri"] = "[bold red]BLOCKED / UNMAPPED[/bold red]"
    type_and_run(
        "python3 registry_control_plane.py revoke",
        stage4, 9, "SecOps Emergency Revocation (Purge Outbound Binding & MCP Service)",
        hud_state, mode
    )

    type_and_run(
        "python3 dynamic_mcp_agent.py",
        stage4, 10, "Agent Invocations Instantly Blocked at Runtime by Central Registry",
        hud_state, mode
    )

    # Restore ready-state for next run or recording take
    hud_state["binding_state"] = "[bold green]APPROVED & BOUND (Restored Initial Ready-State)[/bold green]"
    hud_state["physical_uri"] = ledger_v1_url
    type_and_run(
        "python3 registry_control_plane.py onboard-all",
        stage4, 11, "Reset Environment to Initial Clean v1 Ready-State for Next Recording Take",
        hud_state, mode
    )

    if mode != "non-interactive":
        console.clear()

    console.print(Panel(
        f"[bold green]✓ ALL 4 STAGES & 11 COMMANDS EXECUTED SUCCESSFULLY![/bold green]\n"
        f"Environment reset to clean v1 ready-state in enterprise production.\n"
        f"You are completely ready to film Advent of Agents Season 3 — Day 19!",
        title="🎬 Theatrical Stage Show Complete",
        border_style="green"
    ))


def main():
    parser = argparse.ArgumentParser(description="Day 19 Theatrical Stage Show Driver")
    parser.add_argument(
        "--live-keys", action="store_true",
        help="HackerTyper mode: tap any keyboard keys to type command"
    )
    parser.add_argument(
        "--non-interactive", "-y", action="store_true",
        help="Headless mode: bypass keypresses and execute immediately"
    )

    args = parser.parse_args()

    mode = "auto"
    if args.non_interactive:
        mode = "non-interactive"
    elif args.live_keys:
        mode = "live-keys"

    run_stage_show(mode)


if __name__ == "__main__":
    main()
