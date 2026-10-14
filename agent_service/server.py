import asyncio
import base64
import json
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

import google.auth
import google.auth.transport.requests
from google.genai import types

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

app = FastAPI(
    title="SecOps Compliance & Release Auditor Agent",
    description="Autonomous Agent deployed to Google Cloud Run with Agent Identity & Agent Registry Governance",
    version="1.0.0"
)

PROJECT_ID = os.environ.get("PROJECT_ID", "bu2-prod-data")
REGION = os.environ.get("REGION", "us-central1")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "918024802560")
PARENT = f"projects/{PROJECT_ID}/locations/{REGION}"
SOURCE_AGENT_URN = os.environ.get("SOURCE_AGENT_URN", "urn:agent:secops-auditor")
TARGET_TOOL_URN = os.environ.get("TARGET_TOOL_URN", "urn:mcp:github-mcp")
AGENT_REGISTRY_MCP_URL = os.environ.get("AGENT_REGISTRY_MCP_URL", "https://agentregistry.googleapis.com/mcp")

# Vertex AI settings
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"


def get_gcp_access_token() -> str:
    """Retrieve Google OAuth2 token using Cloud Run Workload Identity."""
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception:
        pass
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"}
            )
            if res.status_code == 200:
                return res.json().get("access_token")
    except Exception as e:
        raise RuntimeError(f"Failed to acquire GCP access token: {e}")


def get_id_token_for_audience(audience_url: str) -> str:
    """Retrieve Cloud Run OIDC ID token for service-to-service IAM invocation."""
    parsed = urlparse(audience_url)
    root_aud = f"{parsed.scheme}://{parsed.netloc}"
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(
                f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={root_aud}",
                headers={"Metadata-Flavor": "Google"}
            )
            if res.status_code == 200 and res.text.strip():
                return res.text.strip()
    except Exception:
        pass
    try:
        import google.oauth2.id_token
        auth_req = google.auth.transport.requests.Request()
        return google.oauth2.id_token.fetch_id_token(auth_req, root_aud)
    except Exception:
        pass
    return get_gcp_access_token()


def retrieve_secret_pat() -> str:
    """Retrieve managed GitHub PAT from Secret Manager using Agent Identity."""
    token = get_gcp_access_token()
    url = f"https://secretmanager.googleapis.com/v1/projects/{PROJECT_ID}/secrets/github-mcp-pat/versions/latest:access"
    try:
        with httpx.Client(timeout=5.0) as client:
            res = client.get(url, headers={"Authorization": f"Bearer {token}"})
            if res.status_code == 200:
                data = res.json().get("payload", {}).get("data", "")
                return base64.b64decode(data).decode("utf-8").strip()
    except Exception:
        pass
    return os.environ.get("GITHUB_PAT", "")


def call_registry_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call Agent Registry Remote MCP Server tools/call endpoint."""
    token = get_gcp_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT_ID,
        "Content-Type": "application/json"
    }
    body = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000000,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(AGENT_REGISTRY_MCP_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Agent Registry error: {data['error']}")
        content = data.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return data.get("result", {})


class AuditRequest(BaseModel):
    repo_full_name: str = "arobinson12/advent-of-agents-s3-day19-mcp-governance"
    query: Optional[str] = "Audit repository release readiness and security posture."


@app.get("/health")
def health():
    return {
        "status": "HEALTHY",
        "service": "secops-auditor",
        "environment": "Google Cloud Run",
        "identity": f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com",
        "model": "gemini-3.8-flash"
    }


@app.get("/card")
@app.get("/a2a/card")
def get_card():
    """Return official A2A Agent Card."""
    card_path = os.path.join(os.path.dirname(__file__), "specs/agent-card.json")
    if os.path.exists(card_path):
        with open(card_path, "r") as f:
            return json.load(f)
    return {
        "name": "secops-auditor",
        "version": "1.0.0",
        "description": "Autonomous SecOps Auditor Agent deployed to Google Cloud Run",
        "skills": [{"id": "audit_github_release", "name": "Audit GitHub Release & Security"}]
    }


@app.post("/a2a")
@app.post("/audit")
async def execute_governed_audit(request: AuditRequest):
    """
    Executes the autonomous auditing flow directly within Google Cloud:
    1. Validates Outbound Binding via Agent Registry Remote MCP
    2. Dynamically resolves target MCP URL (v1 or v2)
    3. Retrieves AuthProvider credentials from Secret Manager
    4. Connects via Google ADK McpToolset (Streamable HTTP)
    5. Analyzes with Gemini 3.8 Flash via Vertex AI and returns audit report
    """
    repo = request.repo_full_name
    
    # 1. Validate Outbound Binding
    bindings_data = call_registry_tool("fetch_available_bindings", {
        "parent": PARENT,
        "sourceIdentifier": SOURCE_AGENT_URN
    })
    bindings = bindings_data.get("bindings", [])
    if not bindings:
        raise HTTPException(
            status_code=403,
            detail=f"[REVOKED / NO OUTBOUND BINDING] Central Governance revoked Outbound Binding for '{SOURCE_AGENT_URN}'!"
        )
    active_binding = bindings[0]
    auth_provider_ref = active_binding.get("authProviderBinding", {}).get("authProvider", "github-auth")

    # 2. Dynamically resolve target MCP endpoint
    search_data = call_registry_tool("search_mcp_servers", {
        "parent": PARENT,
        "searchString": "github"
    })
    servers = search_data.get("mcpServers", [])
    if not servers:
        raise HTTPException(
            status_code=404,
            detail="[REVOKED / NOT FOUND] Central registry returned 0 approved endpoints for 'github'."
        )
    server = servers[0]
    discovered_url = server["interfaces"][0]["url"]

    # 3. Retrieve managed AuthProvider credentials and Cloud Run OIDC ID token
    github_pat = retrieve_secret_pat()
    id_token = get_id_token_for_audience(discovered_url)

    mcp_headers = {
        "Authorization": f"Bearer {id_token}",
        "X-GitHub-Token": github_pat,
        "X-Managed-Auth-Provider": "github-auth",
        "Accept": "application/json, text/event-stream"
    }

    # 4. Connect via Google ADK McpToolset
    conn_params = StreamableHTTPConnectionParams(url=discovered_url, headers=mcp_headers)
    toolset = McpToolset(connection_params=conn_params)

    agent = Agent(
        name="SecOpsGitHubAuditorCloud",
        model="gemini-3.8-flash",
        instruction=(
            "You are the cloud-deployed enterprise SecOps and compliance auditor running in Google Cloud Run. "
            "When auditing repository security, always call inspect_github_repo_security and report the exact "
            "repository status, server version, default branch, latest commit SHA & author, and security audit notes returned."
        ),
        tools=[toolset]
    )

    runner = Runner(agent=agent, app_name="cloud_secops", session_service=InMemorySessionService())
    session = await runner.session_service.create_session(app_name="cloud_secops", user_id="cloud_admin")

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=f"Audit repository '{repo}'. Be specific about the server version and security audit notes.")]
    )

    agent_replies = []
    async for event in runner.run_async(session_id=session.id, user_id="cloud_admin", new_message=user_content):
        if hasattr(event, "content") and event.content:
            for p in event.content.parts:
                if p.text:
                    agent_replies.append(p.text)

    response_text = "\n".join(agent_replies)

    return {
        "status": "SUCCESS",
        "agent_deployment": "Google Cloud Run (Serverless Autonomous Agent)",
        "agent_service": f"projects/{PROJECT_ID}/locations/{REGION}/services/secops-auditor",
        "agent_identity": f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com",
        "source_agent_urn": SOURCE_AGENT_URN,
        "discovered_mcp_url": discovered_url,
        "enforced_binding": active_binding.get("name"),
        "bound_auth_provider": auth_provider_ref,
        "model": "gemini-3.8-flash",
        "audit_report": response_text
    }
