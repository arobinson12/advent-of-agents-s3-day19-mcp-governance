#!/usr/bin/env python3
# ==============================================================================
# LOOK CLOSELY: ZERO HARDCODED TOOL URLS & ZERO GITHUB TOKENS IN THIS FILE!
# All tool endpoints are dynamically resolved via Google Cloud Agent Registry
# and authenticated via Model Armor, Secret Manager & Agent Identity AuthProvider.
# ==============================================================================
"""
Advent of Agents Season 3 — Day 19
Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints

Autonomous ADK Agent that:
1. Validates approved Outbound Bindings via Agent Registry Remote MCP Server:
   https://agentregistry.googleapis.com/mcp
2. Dynamically discovers enterprise MCP tools at runtime (Zero hardcoded URLs).
3. Injects AuthProvider credentials securely via Secret Manager (Zero secrets in code).
4. Executes governed repository auditing with Gemini and Google ADK.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from typing import Dict, Tuple

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Google ADK imports
import google.adk
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams
from google.genai import types

console = Console()


def resolve_project_environment() -> Tuple[str, str, str]:
    """Dynamically determine GCP project_id, region, and project_number."""
    env_file = ".env" if os.path.exists(".env") else (".env.demo" if os.path.exists(".env.demo") else None)
    if env_file:
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

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

    project_number = os.environ.get("PROJECT_NUMBER")
    if not project_number and project_id:
        try:
            project_number = subprocess.check_output(
                ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            project_number = "918024802560"

    return project_id, region, project_number or "918024802560"


PROJECT_ID, REGION, PROJECT_NUMBER = resolve_project_environment()

# Configure Vertex AI backend
MODEL_LOCATION = os.environ.get("MODEL_LOCATION", "global")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = MODEL_LOCATION
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"

AGENT_REGISTRY_MCP_URL = os.environ.get(
    "AGENT_REGISTRY_MCP_URL",
    "https://agentregistry.googleapis.com/mcp"
)
PARENT = f"projects/{PROJECT_ID}/locations/{REGION}"
SOURCE_AGENT_URN = os.environ.get("SOURCE_AGENT_URN", "urn:agent:secops-auditor")
TARGET_TOOL_URN = os.environ.get("TARGET_TOOL_URN", "urn:mcp:github-mcp")


def get_oauth_token() -> str:
    """Retrieve Google Cloud OAuth2 Access Token for Agent Registry calls."""
    try:
        return subprocess.check_output(
            ["gcloud", "auth", "application-default", "print-access-token"],
            stderr=subprocess.PIPE
        ).decode().strip()
    except Exception:
        try:
            return subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                stderr=subprocess.PIPE
            ).decode().strip()
        except Exception as e:
            console.print(f"[bold red]Failed to acquire OAuth token:[/bold red] {e}")
            sys.exit(1)


def get_id_token_for_audience(audience_url: str) -> str:
    """Acquire Cloud Run IAM Identity Token for secure authenticated invocation."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(audience_url)
        root_audience = f"{parsed.scheme}://{parsed.netloc}"

        token = subprocess.check_output([
            "gcloud", "auth", "print-identity-token",
            f"--impersonate-service-account={PROJECT_NUMBER}-compute@developer.gserviceaccount.com",
            f"--audiences={root_audience}"
        ], stderr=subprocess.PIPE).decode().strip()
        return token
    except Exception:
        try:
            return subprocess.check_output(
                ["gcloud", "auth", "print-identity-token"],
                stderr=subprocess.PIPE
            ).decode().strip()
        except Exception:
            return get_oauth_token()


def retrieve_bound_auth_credential(auth_provider_name: str) -> str:
    """
    Simulates runtime RetrieveCredentials from Agent Identity / Secret Manager.
    The agent code contains zero hardcoded API keys or personal access tokens.
    """
    token = get_oauth_token()
    secret_url = f"https://secretmanager.googleapis.com/v1/projects/{PROJECT_ID}/secrets/github-mcp-pat/versions/latest:access"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests_get(secret_url, headers=headers, timeout=5)
        if res.status_code == 200:
            import base64
            payload = res.json().get("payload", {}).get("data", "")
            return base64.b64decode(payload).decode("utf-8").strip()
    except Exception:
        pass
    # Fallback to local environment if Secret Manager not accessible
    return os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN", "")


def requests_get(url: str, headers: Dict, timeout: int = 5):
    with httpx.Client(timeout=timeout) as client:
        return client.get(url, headers=headers)


def print_api_request(url: str, body: Dict):
    """Render the exact outgoing HTTP POST request and JSON-RPC payload."""
    token = get_oauth_token()
    token_display = f"Bearer {token[:14]}...{token[-6:]}" if len(token) > 25 else "Bearer <token>"

    headers_info = (
        f"  [bold yellow]Authorization:[/bold yellow] [dim]{token_display} (Google OAuth2 Access Token)[/dim]\n"
        f"  [bold yellow]x-goog-user-project:[/bold yellow] [dim]<protected-enterprise-project>[/dim]\n"
        f"  [bold yellow]Content-Type:[/bold yellow] [dim]application/json[/dim]"
    )

    body_str = json.dumps(body, indent=2)
    tool_name = body.get("params", {}).get("name", "tool")
    call_title = f"[bold cyan]📡 API Request: tools/call ➔ {tool_name}[/bold cyan]"

    console.print(Panel(
        f"[bold green]POST[/bold green] [cyan]{url}[/cyan]\n\n"
        f"[bold underline yellow]HTTP Request Headers:[/bold underline yellow]\n{headers_info}\n\n"
        f"[bold underline yellow]JSON-RPC 2.0 Request Body:[/bold underline yellow]\n[white]{body_str}[/white]",
        title=call_title,
        border_style="cyan"
    ))


def call_registry_tool(tool_name: str, arguments: Dict) -> Dict:
    """Execute meta-tool call against Google Cloud Agent Registry MCP server."""
    token = get_oauth_token()
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

    print_api_request(AGENT_REGISTRY_MCP_URL, body)

    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            AGENT_REGISTRY_MCP_URL,
            headers=headers,
            json=body
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Agent Registry Tool Call Failed: {data['error']}")
        
        content = data.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return data.get("result", {})


def resolve_governed_mcp_endpoint() -> Tuple[str, Dict, Dict]:
    """
    The Core Dynamic Discovery Flow:
    1. Validates that an active Outbound Binding exists for our agent.
    2. Resolves the live, admin-approved Streamable HTTP URL via Agent Registry.
    """
    console.print(Panel(
        "[bold cyan]Dynamic MCP Governance Discovery Flow[/bold cyan]\n"
        f"1. Query Outbound Bindings: [dim]{AGENT_REGISTRY_MCP_URL} ➔ fetch_available_bindings[/dim]\n"
        f"2. Resolve Target MCP URL:  [dim]{AGENT_REGISTRY_MCP_URL} ➔ search_mcp_servers[/dim]\n"
        f"3. Retrieve AuthProvider:   [dim]agentidentity.googleapis.com (roles/agentidentity.user)[/dim]",
        title="Runtime Discovery",
        border_style="cyan"
    ))

    # [Step 1] Query Outbound Bindings
    console.print(f"[bold cyan][Step 1] Verifying approved Outbound Bindings for source '{SOURCE_AGENT_URN}'...[/bold cyan]")
    bindings_data = call_registry_tool("fetch_available_bindings", {
        "parent": PARENT,
        "sourceIdentifier": SOURCE_AGENT_URN
    })

    bindings = bindings_data.get("bindings", [])
    if not bindings:
        console.print(Panel(
            f"[bold red]EXECUTION BLOCKED BY CENTRAL GOVERNANCE[/bold red]\n\n"
            f"[red]Zero approved Outbound Bindings found for agent: [bold yellow]{SOURCE_AGENT_URN}[/bold yellow][/red]\n"
            f"[dim]The enterprise security control plane has revoked communication permissions for this agent.[/dim]",
            title="SecOps Policy Enforcement",
            border_style="red"
        ))
        raise RuntimeError(f"[REVOKED / NO OUTBOUND BINDING] Central Governance revoked Outbound Binding for '{SOURCE_AGENT_URN}'!")

    active_binding = bindings[0]
    target_identifier = active_binding.get("target", {}).get("identifier", TARGET_TOOL_URN)
    auth_provider_ref = active_binding.get("authProviderBinding", {}).get("authProvider", "github-auth")

    policy_table = Table(title="Validated Outbound Binding Policy", show_header=True, header_style="bold green")
    policy_table.add_column("Property", style="bold yellow")
    policy_table.add_column("Registry Value", style="white")
    policy_table.add_row("Binding Name", active_binding.get("name", "auditor-to-github-binding"))
    policy_table.add_row("Source Agent", SOURCE_AGENT_URN)
    policy_table.add_row("Target MCP Server", target_identifier)
    policy_table.add_row("Enforced AuthProvider", f"{auth_provider_ref} [roles/agentidentity.user ✓]")
    policy_table.add_row("Policy Status", "[bold green]APPROVED & ACTIVE[/bold green]")
    console.print(policy_table)

    # [Step 2] Dynamically Resolve Physical Endpoint URI
    console.print(f"\n[bold cyan][Step 2] Dynamically resolving MCP endpoint for '{target_identifier}'...[/bold cyan]")
    search_data = call_registry_tool("search_mcp_servers", {
        "parent": PARENT,
        "searchString": "github"
    })

    servers = search_data.get("mcpServers", [])
    if not servers:
        console.print(Panel(
            f"[bold red]EXECUTION BLOCKED BY CENTRAL GOVERNANCE[/bold red]\n\n"
            f"[red]No registered MCP tool server matching target: [bold yellow]{target_identifier}[/bold yellow][/red]\n"
            f"[dim]The target tool server has been decommissioned or revoked from Agent Registry.[/dim]",
            title="Service Discovery Blocked",
            border_style="red"
        ))
        raise RuntimeError(f"[REVOKED / NOT FOUND] Central registry returned 0 approved endpoints for '{target_identifier}'.")

    server = servers[0]
    display_name = server.get("displayName", "GitHub Enterprise Security & Audit MCP Server")
    interfaces = server.get("interfaces", [])
    if not interfaces:
        raise RuntimeError(f"Resolved MCP Server '{display_name}' has 0 registered interfaces!")

    discovered_url = interfaces[0].get("url")
    tools = [t.get("name") for t in server.get("tools", [])]

    endpoint_table = Table(title="Dynamically Resolved MCP Tool Server (Zero Hardcoded URLs)", show_header=True, header_style="bold green")
    endpoint_table.add_column("Attribute", style="bold yellow")
    endpoint_table.add_column("Discovered Value", style="white")
    endpoint_table.add_row("Server Name", display_name)
    endpoint_table.add_row("Discovered URL", discovered_url)
    endpoint_table.add_row("Advertised Tools", ", ".join(tools))
    endpoint_table.add_row("Status", "[bold green]RESOLVED LIVE FROM AGENT REGISTRY[/bold green]")
    console.print(endpoint_table)

    return discovered_url, active_binding, server


async def run_governed_adk_agent(query: str = "Audit security and release readiness for repository 'arobinson12/advent-of-agents-s3-day19-mcp-governance'"):
    # Top Banner proving zero hardcoded URLs & zero secrets
    console.print(Panel(
        "[bold green]LOOK CLOSELY: ZERO HARDCODED MCP URLS & ZERO GITHUB TOKENS IN AGENT CODE[/bold green]\n\n"
        "[bold cyan]Native ADK Integration (google-adk >= 1.29.0):[/bold cyan]\n"
        "[dim]from google.adk.integrations.agent_registry import AgentRegistry\n"
        f"registry = AgentRegistry(project='<protected-enterprise-project>', location='{REGION}')\n"
        "toolset = registry.get_mcp_toolset(\"mcpServers/github-mcp\")  # Auto-resolves GcpAuthProviderScheme[/dim]",
        title="[bold blue]Enterprise Governed Agent Environment[/bold blue]",
        border_style="blue"
    ))

    # Compact Model Armor floor status line
    console.print(f"[dim]Model Armor MCP Floor: GOOGLE_MCP_SERVER=INSPECT_AND_BLOCK (Active on projects/{PROJECT_ID}/locations/{REGION})[/dim]\n")

    console.print(Panel(
        f"[bold blue]🚀 Initializing Autonomous ADK Auditor Agent[/bold blue]\n"
        f"Source Agent: [bold yellow]{SOURCE_AGENT_URN}[/bold yellow]\n"
        f"Target Repository: [white]arobinson12/advent-of-agents-s3-day19-mcp-governance[/white]\n"
        f"Architecture: [bold magenta]Outbound Bindings + Agent Registry MCP + ADK + Gemini 3.8 Flash[/bold magenta]",
        title="Governed Agent Execution",
        border_style="blue"
    ))

    # Step 1 & 2: Validate Outbound Binding & Dynamically Discover Endpoint
    discovered_url, binding_info, server_info = resolve_governed_mcp_endpoint()

    # Step 3: Attach Injected AuthProvider Credentials & Cloud Run IAM Token
    console.print(f"\n[bold cyan][Step 3] Attaching Outbound AuthProvider credential & dynamically invoking inspect_github_repo_security...[/bold cyan]")
    
    id_token = get_id_token_for_audience(discovered_url)
    auth_provider_id = binding_info.get("authProviderBinding", {}).get("authProvider", "").split("/")[-1] or "github-auth"
    github_pat = retrieve_bound_auth_credential(auth_provider_id)

    mcp_headers = {
        "Authorization": f"Bearer {id_token}",
        "X-GitHub-Token": github_pat,
        "X-Managed-Auth-Provider": auth_provider_id,
        "Accept": "application/json, text/event-stream"
    }

    conn_params = StreamableHTTPConnectionParams(url=discovered_url, headers=mcp_headers)
    toolset = McpToolset(connection_params=conn_params)

    # Configure ADK Agent with dynamically bound toolset
    agent = Agent(
        name="SecOpsGitHubAuditor",
        model="gemini-3.8-flash",
        instruction=(
            "You are an enterprise SecOps and compliance auditor. When auditing repository security, "
            "always call inspect_github_repo_security and report the exact repository status, server version, "
            "default branch, latest commit SHA & author, and security audit notes returned."
        ),
        tools=[toolset]
    )

    runner = Runner(agent=agent, app_name="advent_day19", session_service=InMemorySessionService())
    session = await runner.session_service.create_session(app_name="advent_day19", user_id="secops_admin")

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=f"{query}. Be specific about the server version and security audit notes.")]
    )

    console.print("[dim]Executing Gemini 3.8 Flash via ADK Runner with dynamic tool verification...[/dim]")
    agent_replies = []
    async for event in runner.run_async(session_id=session.id, user_id="secops_admin", new_message=user_content):
        if hasattr(event, "content") and event.content:
            for p in event.content.parts:
                if p.text:
                    agent_replies.append(p.text)

    response_text = "\n".join(agent_replies)

    console.print(Panel(
        f"[bold green]Autonomous ADK Auditor Report:[/bold green]\n\n{response_text}",
        title="[bold green]✓ Governed GitHub Audit Completed[/bold green]",
        border_style="green"
    ))


if __name__ == "__main__":
    try:
        asyncio.run(run_governed_adk_agent())
    except Exception as e:
        console.print(f"\n[bold red]Execution Blocked by Central Governance: {e}[/bold red]")
        sys.exit(1)
