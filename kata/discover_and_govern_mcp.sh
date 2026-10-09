#!/usr/bin/env bash
# ==============================================================================
# Advent of Agents Day 19 Kata: 300-Second Dynamic MCP Governance & Outbound Bindings
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo 'bu2-prod-data')}"
REGION="${REGION:-us-central1}"
PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null || echo '918024802560')}"
REGISTRY_URL="https://agentregistry.googleapis.com/mcp"
TOKEN=$(gcloud auth application-default print-access-token)
SOURCE_AGENT_URN="${SOURCE_AGENT_URN:-urn:agent:finserv-auditor}"

echo "=== 1. Verify Model Armor Floor Setting ==="
curl -s -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  "https://modelarmor.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/floorSetting"
echo ""

echo "=== 2. Inspect Approved Outbound Bindings ==="
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${REGISTRY_URL}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "fetch_available_bindings",
      "arguments": {
        "parent": "projects/'"${PROJECT_ID}"'/locations/'"${REGION}"'",
        "sourceIdentifier": "'"${SOURCE_AGENT_URN}"'"
      }
    }
  }'
echo ""

echo "=== 3. Discover Tools via Agent Registry Remote MCP Server ==="
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${REGISTRY_URL}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_mcp_servers",
      "arguments": {
        "parent": "projects/'"${PROJECT_ID}"'/locations/'"${REGION}"'",
        "searchString": "ledger"
      }
    }
  }'
echo ""

echo "=== 4. Zero-Downtime Cutover to v2 ==="
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${REGISTRY_URL}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "update_service",
      "arguments": {
        "service": {
          "name": "projects/'"${PROJECT_ID}"'/locations/'"${REGION}"'/services/finserv-ledger-mcp",
          "interfaces": [
            {
              "url": "https://finserv-ledger-mcp-v2-'"${PROJECT_NUMBER}"'.'"${REGION}"'.run.app/mcp",
              "protocolBinding": "JSONRPC"
            }
          ]
        },
        "updateMask": "interfaces"
      }
    }
  }'
echo ""

echo "=== 5. Emergency Outbound Binding & Service Revocation ==="
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${REGISTRY_URL}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "delete_binding",
      "arguments": {
        "name": "projects/'"${PROJECT_ID}"'/locations/'"${REGION}"'/bindings/finserv-auditor-to-ledger-binding"
      }
    }
  }'
echo ""
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "x-goog-user-project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${REGISTRY_URL}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "delete_service",
      "arguments": {
        "name": "projects/'"${PROJECT_ID}"'/locations/'"${REGION}"'/services/finserv-ledger-mcp"
      }
    }
  }'
echo ""
