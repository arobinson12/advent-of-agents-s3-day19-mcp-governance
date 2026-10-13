#!/usr/bin/env bash
# ==============================================================================
# Advent of Agents Season 3 — Day 19
# Pipeline 1: Zero-Touch Auto-Ingest (Cloud Run & GKE Workload Auto-Discovery)
# ==============================================================================
# This script deploys the FastMCP Streamable HTTP servers for GitHub (v1 and v2)
# to Google Cloud Run, demonstrating Pipeline 1 of Agent Registry Ingestion.
#
# GOOGLE CLOUD AUTO-DISCOVERY FLAGS & LABELS:
# 1. Cloud Run MCP Server Auto-Discovery:
#    gcloud run deploy github-mcp-v1 \
#      --image=... \
#      --functional-type=mcp-server \
#      --set-labels="registry.cloud.google.com/functional-type=mcp-server"
#
# 2. Cloud Run Autonomous Agent Auto-Discovery:
#    gcloud run deploy secops-auditor \
#      --image=... \
#      --functional-type=agent \
#      --identity-type=agent-identity \
#      --set-labels="registry.cloud.google.com/functional-type=agent"
# ==============================================================================

set -eo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set and could not be determined from gcloud."
  exit 1
fi

echo "================================================================================"
echo " Deploying FastMCP GitHub Servers to Cloud Run (Pipeline 1: Auto-Discovery) "
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

  # Deploy to Cloud Run with Secret Manager binding for GITHUB_PAT and functional-type label
  gcloud run deploy "$SERVICE_NAME" \
    --source="$SOURCE_DIR" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --no-allow-unauthenticated \
    --set-secrets="GITHUB_PAT=github-mcp-pat:latest" \
    --labels="functional-type=mcp-server,version=${VERSION_TAG}" \
    --quiet

  echo "✓ Deployed ${SERVICE_NAME} with registry.cloud.google.com/functional-type label"

  local URL
  URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
  echo "  Base URL: ${URL}"
  echo "  Streamable HTTP MCP Endpoint: ${URL}/mcp"
}

# 1. Deploy GitHub MCP v1 (Baseline)
deploy_service "github-mcp-v1" "mcp_servers/github_v1" "v1"

# 2. Deploy GitHub MCP v2 (Zero-Trust Hardened)
deploy_service "github-mcp-v2" "mcp_servers/github_v2" "v2"

V1_URL=$(gcloud run services describe github-mcp-v1 --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")/mcp
V2_URL=$(gcloud run services describe github-mcp-v2 --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")/mcp

echo ""
echo "================================================================================"
echo " Cloud Run GitHub MCP Servers Successfully Deployed!"
echo " GITHUB_V1_URL: ${V1_URL}"
echo " GITHUB_V2_URL: ${V2_URL}"
echo "================================================================================"
