#!/usr/bin/env python3
# ==============================================================================
# Advent of Agents Day 19 Kata: Autonomous Agent with ZERO Hardcoded URLs
# ==============================================================================
import asyncio
import json
import os
import subprocess
import httpx
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams
from google.genai import types

PROJECT_ID = os.environ.get("PROJECT_ID", subprocess.check_output(["gcloud", "config", "get-value", "project"]).decode().strip())
REGION = os.environ.get("REGION", "us-central1")
SOURCE_AGENT_URN = os.environ.get("SOURCE_AGENT_URN", "urn:agent:finserv-auditor")

# Configure Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("MODEL_LOCATION", "global")
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"

def resolve_governed_tool():
    token = subprocess.check_output(["gcloud", "auth", "application-default", "print-access-token"]).decode().strip()
    headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": PROJECT_ID}

    # 1. Validate Outbound Binding
    b_resp = httpx.post("https://agentregistry.googleapis.com/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "fetch_available_bindings", "arguments": {
            "parent": f"projects/{PROJECT_ID}/locations/{REGION}", "sourceIdentifier": SOURCE_AGENT_URN
        }}
    }, headers=headers)
    bindings = json.loads(b_resp.json()["result"]["content"][0]["text"]).get("bindings", [])
    if not bindings:
        raise RuntimeError("Blocked by Central Governance: [REVOKED / NO OUTBOUND BINDING]!")

    # 2. Dynamically Resolve Tool Endpoint
    s_resp = httpx.post("https://agentregistry.googleapis.com/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "search_mcp_servers", "arguments": {
            "parent": f"projects/{PROJECT_ID}/locations/{REGION}", "searchString": "ledger"
        }}
    }, headers=headers)
    servers = json.loads(s_resp.json()["result"]["content"][0]["text"]).get("mcpServers", [])
    if not servers:
        raise RuntimeError("No approved tool found!")
    return servers[0]["interfaces"][0]["url"]

async def main():
    # 1. Discover Tool Dynamically & Validate Outbound Binding (Zero Hardcoded URLs!)
    discovered_url = resolve_governed_tool()
    print(f"[DISCOVERED] Approved Tool Endpoint: {discovered_url}")

    # 2. Acquire Cloud Run Identity Token
    audience = discovered_url.split("/mcp")[0]
    try:
        id_token = subprocess.check_output([
            "gcloud", "auth", "print-identity-token",
            f"--audiences={audience}"
        ], stderr=subprocess.PIPE).decode().strip()
    except Exception:
        id_token = subprocess.check_output(["gcloud", "auth", "print-identity-token"]).decode().strip()

    # 3. Bind Dynamic McpToolset to ADK Agent with Managed Auth
    toolset = McpToolset(connection_params=StreamableHTTPConnectionParams(
        url=discovered_url,
        headers={
            "Authorization": f"Bearer {id_token}",
            "X-API-Key": "finserv-secops-key-v1",
            "Accept": "application/json, text/event-stream"
        }
    ))

    agent = Agent(
        name="FinServAuditor",
        model="gemini-3.8-flash",
        instruction="Verify transactions using verify_ledger_transaction and return status and version.",
        tools=[toolset]
    )

    runner = Runner(agent=agent, app_name="kata", session_service=InMemorySessionService())
    session = await runner.session_service.create_session(app_name="kata", user_id="user")
    
    async for event in runner.run_async(
        session_id=session.id, user_id="user",
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="Verify transaction TX-9941")])
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if part.text:
                    print(part.text)

if __name__ == "__main__":
    asyncio.run(main())
