#!/usr/bin/env bash
# ==============================================================================
# Advent of Agents Season 3 — Day 19
# Pipeline 1: Zero-Touch Auto-Ingest (Cloud Run & GKE Workload Auto-Discovery)
# ==============================================================================
# This script deploys the sample FastMCP Streamable HTTP servers (v1 and v2)
# to Google Cloud Run, demonstrating Pipeline 1 of Agent Registry Ingestion.
#
# GOOGLE CLOUD AUTO-DISCOVERY FLAGS & LABELS:
# 1. Cloud Run MCP Server Auto-Discovery:
#    gcloud run deploy finserv-ledger-mcp \
#      --image=... \
#      --functional-type=mcp-server \
#      --set-labels="registry.cloud.google.com/functional-type=mcp-server"
#
# 2. Cloud Run Autonomous Agent Auto-Discovery:
#    gcloud run deploy finserv-auditor-agent \
#      --image=... \
#      --functional-type=agent \
#      --identity-type=agent-identity \
#      --set-labels="registry.cloud.google.com/functional-type=agent"
#
# 3. GKE Workload Auto-Discovery:
#    See k8s/gke-auto-register.yaml for:
#      registry.gke.io/functional-type: "MCP_SERVER" | "AGENT"
# ==============================================================================

set -eo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud."
  exit 1
fi

echo "================================================================================"
echo " Deploying FastMCP Ledger Servers to Cloud Run (Pipeline 1: Auto-Discovery) "
echo " Project: $PROJECT_ID | Region: $REGION"
echo "================================================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

deploy_service() {
  local SERVICE_NAME="$1"
  local SOURCE_DIR="$2"
  local VERSION_TAG="$3"

  echo ""
  echo "--> Deploying ${SERVICE_NAME} (${VERSION_TAG})..."
  
  # Attempt deployment with --functional-type=mcp-server if supported,
  # falling back gracefully to standard deployment with cloud labels.
  if gcloud run deploy "$SERVICE_NAME" \
      --source="$SOURCE_DIR" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --no-allow-unauthenticated \
      --set-labels="registry.cloud.google.com/functional-type=mcp-server,version=${VERSION_TAG}" \
      --functional-type=mcp-server \
      --quiet 2>/dev/null; then
    echo "✓ Deployed ${SERVICE_NAME} with native --functional-type=mcp-server flag"
  else
    # Fallback to standard Cloud Run deployment with functional-type label
    gcloud run deploy "$SERVICE_NAME" \
      --source="$SOURCE_DIR" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --no-allow-unauthenticated \
      --set-labels="registry.cloud.google.com/functional-type=mcp-server,version=${VERSION_TAG}" \
      --quiet
    echo "✓ Deployed ${SERVICE_NAME} with registry.cloud.google.com/functional-type label"
  fi

  local URL
  URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
  echo "  Base URL: ${URL}"
  echo "  Streamable HTTP MCP Endpoint: ${URL}/mcp"
}

# 1. Deploy v1 (Legacy)
deploy_service "finserv-ledger-mcp-v1" "mcp_servers/ledger_v1" "v1"

# 2. Deploy v2 (Hardened)
deploy_service "finserv-ledger-mcp-v2" "mcp_servers/ledger_v2" "v2"

V1_URL=$(gcloud run services describe finserv-ledger-mcp-v1 --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")/mcp
V2_URL=$(gcloud run services describe finserv-ledger-mcp-v2 --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")/mcp

echo ""
echo "================================================================================"
echo " Cloud Run MCP Servers Successfully Deployed!"
echo " LEDGER_V1_URL: ${V1_URL}"
echo " LEDGER_V2_URL: ${V2_URL}"
echo "================================================================================"
