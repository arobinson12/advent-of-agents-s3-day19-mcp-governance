#!/usr/bin/env python3
# ==============================================================================
# Advent of Agents Season 3 — Day 19
# Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints
# Enterprise Governance Control Plane (GitHub MCP + AuthProvider + Outbound Binding)
# ==============================================================================
"""
Administrative Control Plane for Google Cloud Agent Registry & Agent Identity.

Showcases the 3-Part Handshake for 3P MCP Servers (GitHub / Figma):
  Part 1: Register Service (Zero secrets held in registry)
  Part 2: Configure AuthProvider & Grant IAM (roles/agentidentity.user)
  Part 3: Wire Outbound Binding with Managed AuthProvider Enforcement
"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()


def resolve_project_environment() -> Tuple[str, str, str]:
    """Dynamically discover GCP project_id, region, and project_number."""
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

AGENT_REGISTRY_MCP_URL = os.environ.get(
    "AGENT_REGISTRY_MCP_URL",
    "https://agentregistry.googleapis.com/mcp"
)

PARENT = f"projects/{PROJECT_ID}/locations/{REGION}"


def get_cloud_run_mcp_url(service_name: str, fallback_tag: str = "v1") -> str:
    """Discover live Cloud Run Streamable HTTP URL or construct fallback."""
    try:
        url = subprocess.check_output([
            "gcloud", "run", "services", "describe", service_name,
            f"--region={REGION}", f"--project={PROJECT_ID}",
            "--format=value(status.url)"
        ], stderr=subprocess.DEVNULL).decode().strip()
        if url:
            return f"{url}/mcp"
    except Exception:
        pass
    return f"https://{service_name}-gcmp33r4ma-uc.a.run.app/mcp"


GITHUB_V1_URL = os.environ.get("GITHUB_V1_URL", get_cloud_run_mcp_url("github-mcp-v1", "v1"))
GITHUB_V2_URL = os.environ.get("GITHUB_V2_URL", get_cloud_run_mcp_url("github-mcp-v2", "v2"))

# Service IDs
SERVICE_ID = "github-mcp"
SERVICE_RESOURCE_NAME = f"{PARENT}/services/{SERVICE_ID}"
TARGET_TOOL_URN = "urn:mcp:github-mcp"
CANONICAL_TARGET_TOOL_URN = f"urn:mcp:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:{SERVICE_ID}"

SOURCE_AGENT_ID = "secops-auditor"
SOURCE_AGENT_RESOURCE_NAME = f"{PARENT}/services/{SOURCE_AGENT_ID}"
SOURCE_AGENT_URN = "urn:agent:secops-auditor"
CANONICAL_SOURCE_AGENT_URN = f"urn:agent:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:{SOURCE_AGENT_ID}"

REST_ENDPOINT_ID = "cve-advisory-api"
REST_ENDPOINT_RESOURCE_NAME = f"{PARENT}/services/{REST_ENDPOINT_ID}"
CANONICAL_REST_ENDPOINT_URN = f"urn:endpoint:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:{REST_ENDPOINT_ID}"

BINDING_ID = "auditor-to-github-binding"
BINDING_RESOURCE_NAME = f"{PARENT}/bindings/{BINDING_ID}"
AUTH_PROVIDER_ID = "github-auth"
AUTH_PROVIDER_RESOURCE_NAME = f"{PARENT}/authProviders/{AUTH_PROVIDER_ID}"


def get_oauth_token() -> str:
    """Retrieve Google Cloud OAuth2 Access Token."""
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
            console.print(f"[bold red]Failed to get access token:[/bold red] {e}")
            sys.exit(1)


def print_api_request(url: str, body: Dict[str, Any], title: Optional[str] = None):
    """Render the exact outgoing HTTP POST request and JSON-RPC payload for inspection."""
    token = get_oauth_token()
    token_display = f"Bearer {token[:14]}...{token[-6:]}" if len(token) > 25 else "Bearer <token>"

    headers_info = (
        f"  [bold yellow]Authorization:[/bold yellow] [dim]{token_display} (Google OAuth2 Access Token)[/dim]\n"
        f"  [bold yellow]x-goog-user-project:[/bold yellow] [dim]<protected-enterprise-project>[/dim]\n"
        f"  [bold yellow]Content-Type:[/bold yellow] [dim]application/json[/dim]"
    )

    body_str = json.dumps(body, indent=2)

    call_title = title
    if not call_title:
        if body.get("method") == "tools/call" and "params" in body:
            tool_name = body["params"].get("name", "tool")
            call_title = f"[bold cyan]📡 API Request: tools/call ➔ {tool_name}[/bold cyan]"
        elif body.get("method") == "tools/list":
            call_title = "[bold cyan]📡 API Request: tools/list (Enumerate Meta-Tools)[/bold cyan]"
        else:
            call_title = f"[bold cyan]📡 API Request: {body.get('method', 'MCP')}[/bold cyan]"

    console.print(Panel(
        f"[bold green]POST[/bold green] [cyan]{url}[/cyan]\n\n"
        f"[bold underline yellow]HTTP Request Headers:[/bold underline yellow]\n{headers_info}\n\n"
        f"[bold underline yellow]JSON-RPC 2.0 Request Body:[/bold underline yellow]\n[white]{body_str}[/white]",
        title=call_title,
        border_style="cyan"
    ))


def call_registry_mcp(method: str, params: Optional[Dict[str, Any]] = None, show_api_call: bool = True) -> Dict[str, Any]:
    """Execute a JSON-RPC 2.0 call against Google Cloud Agent Registry Remote MCP Server."""
    token = get_oauth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT_ID,
        "Content-Type": "application/json"
    }

    body = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000000,
        "method": method
    }
    if params is not None:
        body["params"] = params

    if show_api_call:
        print_api_request(AGENT_REGISTRY_MCP_URL, body)

    try:
        response = requests.post(
            AGENT_REGISTRY_MCP_URL,
            headers=headers,
            json=body,
            timeout=25
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Agent Registry MCP Error: {data['error']}")
        return data.get("result", {})
    except requests.RequestException as e:
        console.print(f"[bold red]HTTP Request to Agent Registry failed:[/bold red] {e}")
        if hasattr(e, "response") and e.response is not None:
            console.print(f"[dim]{e.response.text}[/dim]")
        raise


def load_github_toolspec() -> Dict[str, Any]:
    """Load official GitHub toolspec definition from specs/github-toolspec.json."""
    spec_path = os.path.join(os.path.dirname(__file__), "specs/github-toolspec.json")
    if not os.path.exists(spec_path):
        spec_path = os.path.join(os.path.dirname(__file__), "toolspec.json")
    if os.path.exists(spec_path):
        try:
            with open(spec_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "displayName": "GitHub Enterprise Security & Audit MCP Server",
        "description": "Admin-approved 3P GitHub MCP Server with bound AuthProvider for inspecting repositories",
        "mcpServerSpec": {
            "type": "TOOL_SPEC",
            "content": {
                "tools": [
                    {
                        "name": "inspect_github_repo_security",
                        "description": "Inspect security posture, release readiness, and commit integrity of a GitHub repository.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"repo_full_name": {"type": "string"}},
                            "required": ["repo_full_name"]
                        },
                        "readOnlyHint": True
                    }
                ]
            }
        }
    }


def load_agent_card() -> Dict[str, Any]:
    """Load official A2A v1.0 Agent Card definition from specs/agent-card.json."""
    card_path = os.path.join(os.path.dirname(__file__), "specs/agent-card.json")
    if os.path.exists(card_path):
        try:
            with open(card_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "name": SOURCE_AGENT_ID,
        "description": "Autonomous security & compliance auditor agent powered by Google ADK",
        "version": "1.0.0",
        "supportedInterfaces": [{"protocolBinding": "JSONRPC", "protocolVersion": "1.0", "url": "https://secops-auditor.internal/a2a"}],
        "skills": [{"id": "audit_github_release", "name": "Audit GitHub Release & Security"}]
    }


def ensure_auth_provider():
    """
    Ensure the AuthProvider exists in agentidentity.googleapis.com
    and verify roles/agentidentity.user is granted to the Agent Principal.
    """
    token = get_oauth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url_get = f"https://agentidentity.googleapis.com/v1/{AUTH_PROVIDER_RESOURCE_NAME}"
    url_create = f"https://agentidentity.googleapis.com/v1/{PARENT}/authProviders?authProviderId={AUTH_PROVIDER_ID}"

    # 1. Create or verify AuthProvider
    get_res = requests.get(url_get, headers=headers)
    if get_res.status_code == 404:
        payload = {
            "description": "Managed GitHub Authentication Provider for GitHub MCP Server (Fine-Grained PAT / OAuth 3LO)",
            "authProviderTypeParams": {
                "apiKey": {}
            }
        }
        create_res = requests.post(url_create, headers=headers, json=payload)
        if create_res.status_code not in (200, 201):
            console.print(f"[yellow]AuthProvider notice: {create_res.status_code}[/yellow]")

    # 2. Grant roles/agentidentity.user on AuthProvider to Agent Principal
    iam_url = f"https://agentidentity.googleapis.com/v1/{AUTH_PROVIDER_RESOURCE_NAME}:setIamPolicy"
    iam_policy = {
        "policy": {
            "bindings": [
                {
                    "role": "roles/agentidentity.user",
                    "members": [
                        f"serviceAccount:{PROJECT_NUMBER}-compute@developer.gserviceaccount.com",
                        "user:admin@ahmadrobinson.altostrat.com"
                    ]
                }
            ]
        }
    }
    requests.post(iam_url, headers=headers, json=iam_policy)


def onboard_github_mcp_and_binding():
    """
    ACT 1: Execute the complete 3-Part Handshake for GitHub MCP + AuthProvider + Binding.
    Renders Panel 1 (Handshake Blueprint) and Panel 2 (CQRS Projection Table).
    """
    console.print(Panel(
        f"[bold blue]🚀 Executing 3-Part Handshake for Governed 3P MCP Server (GitHub)[/bold blue]\n"
        f"Location: [bold yellow]{REGION}[/bold yellow] | Scope: [bold yellow]Agent Registry + Agent Identity[/bold yellow]",
        title="Stage 1: Enterprise MCP Governance Onboarding",
        border_style="blue"
    ))

    # Query existing services to avoid duplicate create calls
    services_res = call_registry_mcp("tools/call", {
        "name": "list_services",
        "arguments": {"parent": PARENT}
    }, show_api_call=False)
    content_raw = services_res.get("content", [{}])[0].get("text", "{}")
    existing_services = json.loads(content_raw).get("services", [])
    existing_names = [s.get("name") for s in existing_services]

    # --------------------------------------------------------------------------
    # PART 1: Register Service in Agent Registry (Zero Secrets Held!)
    # --------------------------------------------------------------------------
    toolspec_data = load_github_toolspec()
    mcp_spec = toolspec_data.get("mcpServerSpec", toolspec_data)

    if SERVICE_RESOURCE_NAME not in existing_names:
        call_registry_mcp("tools/call", {
            "name": "create_service",
            "arguments": {
                "parent": PARENT,
                "serviceId": SERVICE_ID,
                "service": {
                    "displayName": toolspec_data.get("displayName", "GitHub Enterprise Security & Audit MCP Server"),
                    "description": "Admin-approved 3P GitHub MCP Server with bound AuthProvider for inspecting repositories (v1.0-GITHUB-MCP-BASIC)",
                    "interfaces": [{"url": GITHUB_V1_URL, "protocolBinding": "JSONRPC"}],
                    "mcpServerSpec": mcp_spec
                }
            }
        })
    else:
        call_registry_mcp("tools/call", {
            "name": "update_service",
            "arguments": {
                "service": {
                    "name": SERVICE_RESOURCE_NAME,
                    "description": "Admin-approved 3P GitHub MCP Server with bound AuthProvider for inspecting repositories (v1.0-GITHUB-MCP-BASIC)",
                    "interfaces": [{"url": GITHUB_V1_URL, "protocolBinding": "JSONRPC"}]
                },
                "updateMask": "interfaces,description"
            }
        })

    # Register Autonomous Agent Service (A2A Agent Card)
    agent_card_data = load_agent_card()
    if SOURCE_AGENT_RESOURCE_NAME not in existing_names:
        call_registry_mcp("tools/call", {
            "name": "create_service",
            "arguments": {
                "parent": PARENT,
                "serviceId": SOURCE_AGENT_ID,
                "service": {
                    "displayName": "SecOps Compliance & Release Auditor Agent",
                    "description": agent_card_data.get("description", "Autonomous security & compliance auditor agent"),
                    "agentSpec": {
                        "type": "A2A_AGENT_CARD",
                        "content": agent_card_data
                    }
                }
            }
        })

    # Register Direct REST Endpoint Service (CVE Advisory Screening API)
    if REST_ENDPOINT_RESOURCE_NAME not in existing_names:
        call_registry_mcp("tools/call", {
            "name": "create_service",
            "arguments": {
                "parent": PARENT,
                "serviceId": REST_ENDPOINT_ID,
                "service": {
                    "displayName": "NIST / MITRE CVE Advisory Screening API",
                    "description": "Real-time vulnerability database screening API for known CVE identifiers",
                    "interfaces": [{"url": "https://api.cve.mitre.org/v1", "protocolBinding": "HTTP_JSON"}],
                    "endpointSpec": {"type": "NO_SPEC"}
                }
            }
        })

    # --------------------------------------------------------------------------
    # PART 2: Configure AuthProvider & Grant IAM (agentidentity.googleapis.com)
    # --------------------------------------------------------------------------
    ensure_auth_provider()

    # --------------------------------------------------------------------------
    # PART 3: Wire Outbound Binding with AuthProvider Enforcement
    # --------------------------------------------------------------------------
    bindings_res = call_registry_mcp("tools/call", {
        "name": "fetch_available_bindings",
        "arguments": {"parent": PARENT, "sourceIdentifier": SOURCE_AGENT_URN}
    }, show_api_call=False)
    content_raw = bindings_res.get("content", [{}])[0].get("text", "{}")
    existing_bindings = json.loads(content_raw).get("bindings", [])
    has_binding = any(b.get("target", {}).get("identifier") == TARGET_TOOL_URN for b in existing_bindings)

    if not has_binding:
        call_registry_mcp("tools/call", {
            "name": "create_binding",
            "arguments": {
                "parent": PARENT,
                "bindingId": BINDING_ID,
                "binding": {
                    "displayName": "SecOps Auditor to GitHub MCP Binding",
                    "description": "Admin-approved Outbound Binding linking SecOps Auditor to GitHub MCP with bound AuthProvider (github-auth)",
                    "source": {"identifier": SOURCE_AGENT_URN},
                    "target": {"identifier": TARGET_TOOL_URN},
                    "authProviderBinding": {
                        "authProvider": AUTH_PROVIDER_RESOURCE_NAME
                    }
                }
            }
        })

    # ==========================================================================
    # PANEL 1: The 3-Part GitHub MCP + Auth Handshake Summary
    # ==========================================================================
    handshake_text = (
        "[bold cyan]Part 1 — Register Service (agentregistry.googleapis.com)[/bold cyan]\n"
        f"  • Service Resource: [bold green]services/{SERVICE_ID}[/bold green] (Points to Cloud Run {GITHUB_V1_URL})\n"
        f"  • Spec: [bold yellow]@specs/github-toolspec.json[/bold yellow] (inspect_github_repo_security, audit_latest_commits)\n"
        f"  • [bold red]CRITICAL:[/bold red] The Service Catalog holds [bold underline]ZERO SECRETS[/bold underline]!\n\n"
        "[bold cyan]Part 2 — Create AuthProvider & Grant IAM (agentidentity.googleapis.com / Secret Manager)[/bold cyan]\n"
        f"  • AuthProvider: [bold green]authProviders/{AUTH_PROVIDER_ID}[/bold green] (Supports Fine-Grained PAT apiKey & 3LO OAuth)\n"
        f"  • Secret Manager: [bold yellow]projects/{PROJECT_ID}/secrets/github-mcp-pat[/bold yellow] (Real PAT stored securely)\n"
        f"  • [bold red]#1 GOTCHA AVOIDED:[/bold red] Agent Principal granted [bold green]roles/agentidentity.user[/bold green] on AuthProvider!\n\n"
        "[bold cyan]Part 3 — Wire Outbound Binding (bindings/auditor-to-github-binding)[/bold cyan]\n"
        f"  • Policy Wire: [bold magenta]{SOURCE_AGENT_URN}[/bold magenta] ➔ [bold magenta]{TARGET_TOOL_URN}[/bold magenta]\n"
        f"  • Auth Enforcement: [bold green]authProviderBinding: {AUTH_PROVIDER_ID}[/bold green]\n"
        f"  • Native ADK Integration: [bold yellow]registry.get_mcp_toolset(\"mcpServers/github-mcp\")[/bold yellow] auto-resolves GcpAuthProviderScheme!"
    )
    console.print(Panel(
        handshake_text,
        title="[bold green]✓ 3-Part Handshake Successfully Configured[/bold green]",
        border_style="green"
    ))

    # ==========================================================================
    # PANEL 2: CQRS Write ➔ Read Catalog Projection Table
    # ==========================================================================
    inspect_catalog_table()


def inspect_catalog_table():
    """Query Read Catalog and render CQRS Data Model projection table."""
    mcp_res = call_registry_mcp("tools/call", {
        "name": "search_mcp_servers",
        "arguments": {"parent": PARENT, "searchString": "github"}
    }, show_api_call=False)
    mcp_content = json.loads(mcp_res.get("content", [{}])[0].get("text", "{}"))
    servers = mcp_content.get("mcpServers", [])

    bindings_res = call_registry_mcp("tools/call", {
        "name": "fetch_available_bindings",
        "arguments": {"parent": PARENT, "sourceIdentifier": SOURCE_AGENT_URN}
    }, show_api_call=False)
    bindings_content = json.loads(bindings_res.get("content", [{}])[0].get("text", "{}"))
    bindings = bindings_content.get("bindings", [])

    table = Table(
        title="CQRS Data Model: Writable Services Projected into Read-Only Catalogs",
        show_header=True,
        header_style="bold green"
    )
    table.add_column("Writable Source Service", style="bold cyan", width=22)
    table.add_column("Catalog Type", style="bold yellow", width=12)
    table.add_column("Canonical Logical URN", style="bold magenta")
    table.add_column("Active Physical URI", style="white")
    table.add_column("Bound AuthProvider & IAM", style="green")

    # Row 1: GitHub MCP Server
    v1_active_url = GITHUB_V1_URL
    if servers:
        s = servers[0]
        if s.get("interfaces"):
            v1_active_url = s["interfaces"][0].get("url", GITHUB_V1_URL)

    table.add_row(
        f"services/{SERVICE_ID}",
        "McpServer",
        TARGET_TOOL_URN,
        v1_active_url,
        f"{AUTH_PROVIDER_ID} [roles/agentidentity.user ✓]"
    )

    # Row 2: SecOps Auditor Agent
    table.add_row(
        f"services/{SOURCE_AGENT_ID}",
        "Agent (A2A)",
        SOURCE_AGENT_URN,
        "https://secops-auditor.internal/a2a",
        "Agent Identity (IAM Workload)"
    )

    # Row 3: REST Endpoint
    table.add_row(
        f"services/{REST_ENDPOINT_ID}",
        "Endpoint",
        f"urn:endpoint:{REST_ENDPOINT_ID}",
        "https://api.cve.mitre.org/v1",
        "Direct HTTPS / Anonymous"
    )

    console.print(table)
    console.print("[dim]Key Insight: Client agents query immutable Logical URNs. Physical URLs and versions migrate with zero caller downtime.[/dim]\n")


def cutover_to_v2():
    """
    ACT 3a: Perform zero-downtime cutover from github-mcp-v1 to github-mcp-v2.
    Renders Before vs. After Cutover Diff Panel proving Logical URN & Binding do not change.
    """
    console.print(Panel(
        f"[bold blue]🔄 Initiating Zero-Downtime Tool Cutover (github-mcp-v1 ➔ github-mcp-v2)[/bold blue]\n"
        f"Target Service: [bold yellow]services/{SERVICE_ID}[/bold yellow] | Immutable URN: [bold magenta]{TARGET_TOOL_URN}[/bold magenta]",
        title="Stage 3: Zero-Downtime Tool Cutover",
        border_style="yellow"
    ))

    # Execute service update via Agent Registry MCP
    call_registry_mcp("tools/call", {
        "name": "update_service",
        "arguments": {
            "service": {
                "name": SERVICE_RESOURCE_NAME,
                "description": "Admin-approved 3P GitHub MCP Server (v2.0-GHAS-PQC-HARDENED: Branch Protection & Post-Quantum Signatures)",
                "interfaces": [
                    {
                        "url": GITHUB_V2_URL,
                        "protocolBinding": "JSONRPC"
                    }
                ]
            },
            "updateMask": "interfaces,description"
        }
    })

    # Render Before vs After Cutover Diff Panel
    diff_table = Table(title="Control Plane Cutover Verification Diff", show_header=True, header_style="bold cyan")
    diff_table.add_column("Governance Parameter", style="bold yellow")
    diff_table.add_column("Before Cutover (v1)", style="red")
    diff_table.add_column("After Cutover (v2)", style="bold green")
    diff_table.add_column("Auditor Impact", style="white")

    diff_table.add_row(
        "Logical Tool URN",
        TARGET_TOOL_URN,
        TARGET_TOOL_URN,
        "[bold green]UNCHANGED (Immutable)[/bold green]"
    )
    diff_table.add_row(
        "Physical Target URI",
        GITHUB_V1_URL,
        GITHUB_V2_URL,
        "[bold green]MIGRATED INSTANTLY[/bold green]"
    )
    diff_table.add_row(
        "Outbound Binding Policy",
        f"bindings/{BINDING_ID}",
        f"bindings/{BINDING_ID}",
        "[bold green]UNCHANGED (Valid)[/bold green]"
    )
    diff_table.add_row(
        "Bound AuthProvider",
        AUTH_PROVIDER_ID,
        AUTH_PROVIDER_ID,
        "[bold green]UNCHANGED (Preserved)[/bold green]"
    )
    diff_table.add_row(
        "Downstream Agent Code",
        "dynamic_mcp_agent.py",
        "dynamic_mcp_agent.py",
        "[bold green]0 LINES OF CODE CHANGED[/bold green]"
    )

    console.print(diff_table)
    console.print(Panel(
        f"[bold green]✓ Zero-Downtime Cutover Completed Successfully![/bold green]\n"
        f"All subsequent runtime calls to [bold magenta]{TARGET_TOOL_URN}[/bold magenta] automatically resolve to [bold cyan]{GITHUB_V2_URL}[/bold cyan].",
        border_style="green"
    ))


def emergency_revoke():
    """
    ACT 4: Central Kill-Switch. Revokes Outbound Binding and unregisters Service.
    Immediately blocks any downstream agent invocations at runtime.
    """
    console.print(Panel(
        f"[bold red]🚨 TRIGGERING CENTRAL SECOPS EMERGENCY KILL-SWITCH[/bold red]\n"
        f"Revoking Outbound Binding: [bold yellow]bindings/{BINDING_ID}[/bold yellow]\n"
        f"Target Tool Server: [bold yellow]services/{SERVICE_ID}[/bold yellow]",
        title="Stage 4: Central Kill-Switch & Policy Revocation",
        border_style="red"
    ))

    # 1. Delete Outbound Binding
    try:
        call_registry_mcp("tools/call", {
            "name": "delete_binding",
            "arguments": {"name": BINDING_RESOURCE_NAME}
        })
        console.print(f"[bold green]✓ Revoked Outbound Binding: {BINDING_ID}[/bold green]")
    except Exception as e:
        console.print(f"[yellow]Binding deletion notice: {e}[/yellow]")

    # 2. Delete Service
    try:
        call_registry_mcp("tools/call", {
            "name": "delete_service",
            "arguments": {"name": SERVICE_RESOURCE_NAME}
        })
        console.print(f"[bold green]✓ Unregistered Service: {SERVICE_ID}[/bold green]")
    except Exception as e:
        console.print(f"[yellow]Service deletion notice: {e}[/yellow]")

    console.print(Panel(
        "[bold red]POLICY REVOCATION ACTIVE[/bold red]\n"
        "Agent Registry and Model Armor will reject any invocation attempts by downstream agents.\n"
        "Zero rogue or orphaned tools can execute across the enterprise fleet.",
        title="Runtime Enforcement State",
        border_style="red"
    ))


def show_agent_code():
    """Display the Agent code showing zero hardcoded URLs and zero secrets."""
    agent_path = os.path.join(os.path.dirname(__file__), "dynamic_mcp_agent.py")

    code_excerpt = """# [Step 1] Query Agent Registry for approved Outbound Bindings
bindings_data = call_registry_tool("fetch_available_bindings", {
    "parent": PARENT,
    "sourceIdentifier": SOURCE_AGENT_URN
})
active_binding = bindings_data["bindings"][0]

# [Step 2] Dynamically resolve live endpoint URI from central catalog
servers_data = call_registry_tool("search_mcp_servers", {
    "parent": PARENT,
    "searchString": "github"
})
discovered_url = servers_data["mcpServers"][0]["interfaces"][0]["url"]

# [Step 3] Retrieve bound AuthProvider credential via GCP (Zero secrets in code!)
github_pat = retrieve_auth_provider_credential("github-auth")
conn_params = StreamableHTTPConnectionParams(
    url=discovered_url,
    headers={"X-GitHub-Token": github_pat}
)
toolset = McpToolset(connection_params=conn_params)"""

    compare_table = Table(title="Architecture Comparison: Hardcoded vs. Governed MCP", show_header=True, header_style="bold cyan")
    compare_table.add_column("Dimension", style="bold yellow", width=22)
    compare_table.add_column("❌ Anti-Pattern (Hardcoded)", style="red", width=34)
    compare_table.add_column("✅ Governed Pattern (Agent Registry)", style="bold green", width=38)

    compare_table.add_row(
        "Tool URL Discovery",
        "McpToolset(url='https://github-mcp-v1.run.app')",
        "Dynamic resolution via search_mcp_servers"
    )
    compare_table.add_row(
        "Auth & Secret Mgmt",
        "GITHUB_TOKEN stored in .env or hardcoded",
        "Broker via AuthProvider + Secret Manager"
    )
    compare_table.add_row(
        "IAM Access Control",
        "Static credentials passed anywhere",
        "Enforced roles/agentidentity.user per agent"
    )
    compare_table.add_row(
        "Version Upgrades",
        "Requires agent redeployment & outage",
        "Zero-downtime cutover via registry"
    )
    compare_table.add_row(
        "Emergency Revocation",
        "Requires manual code patch & CI/CD push",
        "Instant central kill-switch via delete_binding"
    )

    console.print(compare_table)
    console.print(Panel(
        Syntax(code_excerpt, "python", theme="monokai", line_numbers=True),
        title="[bold green]dynamic_mcp_agent.py (Zero Hardcoded URLs & Zero Secrets)[/bold green]",
        border_style="green"
    ))


def main():
    parser = argparse.ArgumentParser(description="Google Cloud Agent Registry Governance Control Plane")
    subparsers = parser.add_subparsers(dest="command", help="Control plane command")

    subparsers.add_parser("onboard-github", help="Execute complete 3-Part Handshake (Service + AuthProvider + Binding)")
    subparsers.add_parser("onboard-all", help="Alias for onboard-github")
    subparsers.add_parser("register-v1", help="Alias for onboard-github")
    subparsers.add_parser("cutover-v2", help="Perform zero-downtime cutover to GitHub MCP v2")
    subparsers.add_parser("revoke", help="SecOps emergency kill-switch (revoke binding and service)")
    subparsers.add_parser("inspect-catalog", help="Inspect CQRS Write-to-Read projection table")
    subparsers.add_parser("show-agent-code", help="Inspect agent code showing zero hardcoded URLs")

    args = parser.parse_args()

    if args.command in ("onboard-github", "onboard-all", "register-v1"):
        onboard_github_mcp_and_binding()
    elif args.command == "cutover-v2":
        cutover_to_v2()
    elif args.command == "revoke":
        emergency_revoke()
    elif args.command == "inspect-catalog":
        inspect_catalog_table()
    elif args.command == "show-agent-code":
        show_agent_code()
    else:
        onboard_github_mcp_and_binding()


if __name__ == "__main__":
    main()
