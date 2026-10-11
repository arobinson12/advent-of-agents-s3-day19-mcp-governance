#!/usr/bin/env bash
# ==============================================================================
# Advent of Agents Season 3 — Day 19 Theatrical Stage Show Runner
# "Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints"
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Launch Python stage show driver with simulated human typing and persistent HUD
exec python3 "$SCRIPT_DIR/stage_show_driver.py" "$@"
