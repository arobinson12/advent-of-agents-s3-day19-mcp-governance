#!/usr/bin/env bash
# ==============================================================================
# Advent of Agents Season 3 — Day 19 Theatrical Stage Show Runner
# "Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints"
# ==============================================================================

set -eo pipefail

NON_INTERACTIVE=false
if [[ "$1" == "--non-interactive" || "$1" == "-y" ]]; then
  NON_INTERACTIVE=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ANSI Color Codes
CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
MAGENTA='\033[1;35m'
BLUE='\033[1;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

pause_step() {
  if [ "$NON_INTERACTIVE" = false ]; then
    echo -e "${YELLOW}"
    read -p ">> Press [ENTER] to continue to next stage..."
    echo -e "${NC}"
  else
    sleep 2
  fi
}

echo -e "${CYAN}================================================================================${NC}"
echo -e "${BOLD}${MAGENTA}       ADVENT OF AGENTS SEASON 3 — DAY 19: DYNAMIC MCP GOVERNANCE${NC}"
echo -e "${BOLD}${GREEN}        Eliminating Hardcoded Tool Endpoints with Google Cloud Agent Registry${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo ""
echo -e "  ${BOLD}Active GCP Project:${NC} ${PROJECT_ID:-bu2-prod-data}"
echo -e "  ${BOLD}Region:${NC}            ${REGION:-us-central1}"
echo -e "  ${BOLD}Model Armor Floor:${NC} GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK"
echo -e "  ${BOLD}Registry Gateway:${NC}  https://agentregistry.googleapis.com/mcp"
echo ""

pause_step

# ==============================================================================
# ACT 1: THE TRAP — HARDCODED ENDPOINTS VS. CENTRAL GOVERNANCE & BINDINGS
# ==============================================================================
echo -e "${BLUE}================================================================================${NC}"
echo -e "${BOLD}${BLUE}ACT 1: The Trap — Hardcoded Endpoints vs. Outbound Bindings & Governance${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo -e "${YELLOW}[THE PROBLEM]${NC} Hardcoded tool URLs create severe enterprise governance risks:"
echo -e "  1. Fragile Client Agents: DNS or server migration breaks production workflows."
echo -e "  2. Shadow AI / Tool Sprawl: SecOps has zero visibility into endpoints agents invoke."
echo -e "  3. Zero Perimeter Defense: Malicious prompts or hijacked servers execute unchecked."
echo ""
echo -e "${GREEN}[THE GOVERNANCE FIX: 5 PILLARS]${NC}"
echo -e "  1. Tool Registry Onboarding: All 3 paths (1P Auto-Discovery, Compute Auto-Discovery, Declarative ToolSpec)."
echo -e "  2. Agent Registry Remote MCP Server: Universal discovery gateway (https://agentregistry.googleapis.com/mcp)."
echo -e "  3. Outbound Bindings & Managed Auth: Explicit authorization linking agents to vetted tools."
echo -e "  4. Dynamic Runtime Invocation: Google ADK + Gemini 3.8 Flash binding toolsets on-the-fly."
echo -e "  5. Scale Management & Perimeter Protection: Zero-downtime cutover, instant kill-switch, Model Armor Floor Settings."
echo ""

echo -e "${CYAN}--- Step 1.1: Verifying Model Armor Floor Setting Protection ---${NC}"
TOKEN=$(gcloud auth application-default print-access-token)
PROJ="${PROJECT_ID:-bu2-prod-data}"
curl -s -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJ}" \
  https://modelarmor.googleapis.com/v1/projects/${PROJ}/locations/global/floorSetting | \
  python3 -c "
import sys, json
d = json.load(sys.stdin)
print('  Enforcement Active:', d.get('enableFloorSettingEnforcement'))
print('  Integrated Services:', d.get('integratedServices'))
print('  Floor Setting Config:', d.get('googleMcpServerFloorSetting'))
"
echo ""

echo -e "${CYAN}--- Step 1.2: Discovering Built-In Remote MCP Governance Meta-Tools ---${NC}"
python3 registry_control_plane.py list-meta-tools

echo -e "${CYAN}--- Step 1.3: Explaining All 3 Tool Registry Onboarding Paths ---${NC}"
python3 registry_control_plane.py explain-paths

echo -e "${CYAN}--- Step 1.4: Registering Service (Path 3 ToolSpec), Agent, & Outbound Binding ---${NC}"
python3 registry_control_plane.py register-v1

echo -e "${CYAN}--- Step 1.5: Inspecting Active Outbound Bindings & Auth Provider ---${NC}"
python3 registry_control_plane.py inspect-bindings

echo -e "${GREEN}✓ ACT 1 Complete: Agent & Tool registered, Outbound Binding active, Floor Settings enforced.${NC}"
pause_step

# ==============================================================================
# ACT 2: DYNAMIC OUTBOUND BINDING RESOLUTION & TOOL EXECUTION
# ==============================================================================
echo -e "${CYAN}================================================================================${NC}"
echo -e "${BOLD}${CYAN}ACT 2: Dynamic Outbound Binding Resolution in Action (Zero Hardcoded URLs)${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo -e "${YELLOW}[ARCHITECTURAL PROOF]${NC} Inspecting dynamic_mcp_agent.py source code..."
head -n 12 dynamic_mcp_agent.py
echo ""

echo -e "${CYAN}--- Launching Autonomous ADK Agent ---${NC}"
echo -e "Task: \"Verify ledger transaction TX-9941\""
python3 dynamic_mcp_agent.py

echo -e "${GREEN}✓ ACT 2 Complete: Agent validated Outbound Binding & dynamically resolved v1 endpoint.${NC}"
pause_step

# ==============================================================================
# ACT 3: ZERO-DOWNTIME GOVERNANCE CUTOVER (v1 -> v2)
# ==============================================================================
echo -e "${MAGENTA}================================================================================${NC}"
echo -e "${BOLD}${MAGENTA}ACT 3: Zero-Downtime Governance Cutover (v1.0 -> v2.0 Hardened)${NC}"
echo -e "${MAGENTA}================================================================================${NC}"
echo -e "${YELLOW}[SECOPS DIRECTIVE]${NC} Upgrading production tool to v2.0 with Post-Quantum Cryptography (ML-DSA-65)."
echo -e "${YELLOW}Notice: ZERO code changes will be made to client agent code; Outbound Binding is preserved!${NC}"
echo ""

echo -e "${MAGENTA}--- Executing Admin Tool Migration in Agent Registry ---${NC}"
python3 registry_control_plane.py cutover-v2

echo -e "${MAGENTA}--- Executing Same ADK Agent Without Any Code Modifications ---${NC}"
python3 dynamic_mcp_agent.py

echo -e "${GREEN}✓ ACT 3 Complete: Zero-downtime cutover successful! Agent seamlessly routed to v2.${NC}"
pause_step

# ==============================================================================
# ACT 4: OUTBOUND BINDING REVOCATION & CENTRAL QUARANTINE
# ==============================================================================
echo -e "${RED}================================================================================${NC}"
echo -e "${BOLD}${RED}ACT 4: Rogue Tool & Outbound Binding Revocation (Governance Kill Switch)${NC}"
echo -e "${RED}================================================================================${NC}"
echo -e "${YELLOW}[SECOPS EMERGENCY]${NC} Rogue tool or compromised endpoint detected."
echo -e "Admin revokes Outbound Binding and Service registration from Agent Registry remote control plane."
echo ""

echo -e "${RED}--- Revoking Outbound Binding and Service Registration ---${NC}"
python3 registry_control_plane.py revoke

echo -e "${RED}--- Agent Attempts Tool Access Post-Revocation ---${NC}"
python3 dynamic_mcp_agent.py || true

echo ""
echo -e "${CYAN}================================================================================${NC}"
echo -e "${BOLD}${GREEN}               STAGE SHOW SUMMARY & TAKEAWAYS FOR AUDIENCE${NC}"
echo -e "${CYAN}================================================================================${NC}"
echo -e "  1. ${BOLD}Zero Hardcoded URLs:${NC} Eliminates tool sprawl and configuration debt."
echo -e "  2. ${BOLD}All 3 Onboarding Paths:${NC} 1P GCP Auto-Discovery, Compute Auto-Discovery (Cloud Run/GKE), Declarative ToolSpec."
echo -e "  3. ${BOLD}Outbound Bindings:${NC} Explicit whitelist of approved agent-to-tool connections with managed auth."
echo -e "  4. ${BOLD}Agent Registry Remote MCP:${NC} Centralized discovery, versioning, and lifecycle management."
echo -e "  5. ${BOLD}Zero-Downtime Migration:${NC} Repoint endpoints without touching running agent code."
echo -e "  6. ${BOLD}Instant Kill Switch:${NC} Revoking bindings immediately blocks unauthorized agent execution."
echo -e "  7. ${BOLD}Model Armor Floor Settings:${NC} Project-wide perimeter blocking prevents jailbreaks & exfiltration."
echo -e "${CYAN}================================================================================${NC}"
echo ""

echo -e "${YELLOW}--- Resetting Environment to Initial v1 Ready-State for Filming ---${NC}"
python3 registry_control_plane.py register-v1
echo -e "${GREEN}✓ Ready-state restored! You are ready to film Day 19!${NC}"
