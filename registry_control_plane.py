#!/usr/bin/env python3
"""
Agent Registry Control Plane CLI
Advent of Agents Season 3 — Day 19

Manages MCP server registration, source agent records, outbound bindings,
zero-downtime cutover, and instant revocation directly through the Google Cloud
Agent Registry Remote MCP Server endpoint:
  https://agentregistry.googleapis.com/mcp
"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def resolve_project_environment() -> Tuple[str, str, str]:
    """Dynamically determine GCP project_id, region, and project_number."""
    # 1. Load from environment or local .env / .env.demo if present
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
LEDGER_V1_URL = os.environ.get(
    "LEDGER_V1_URL",
    f"https://finserv-ledger-mcp-v1-{PROJECT_NUMBER}.{REGION}.run.app/mcp"
)
LEDGER_V2_URL = os.environ.get(
    "LEDGER_V2_URL",
    f"https://finserv-ledger-mcp-v2-{PROJECT_NUMBER}.{REGION}.run.app/mcp"
)

PARENT = f"projects/{PROJECT_ID}/locations/{REGION}"

# Target MCP Tool Service
SERVICE_ID = "finserv-ledger-mcp"
SERVICE_RESOURCE_NAME = f"{PARENT}/services/{SERVICE_ID}"
TARGET_TOOL_URN = os.environ.get("TARGET_TOOL_URN", "urn:mcp:finserv-ledger")
CANONICAL_TARGET_TOOL_URN = f"urn:mcp:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:{SERVICE_ID}"

# Source Autonomous Agent Service
SOURCE_AGENT_ID = "finserv-auditor-agent"
SOURCE_AGENT_RESOURCE_NAME = f"{PARENT}/services/{SOURCE_AGENT_ID}"
SOURCE_AGENT_URN = os.environ.get("SOURCE_AGENT_URN", "urn:agent:finserv-auditor")
CANONICAL_SOURCE_AGENT_URN = f"urn:agent:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:{SOURCE_AGENT_ID}"

# Outbound Binding
BINDING_ID = "finserv-auditor-to-ledger-binding"
BINDING_RESOURCE_NAME = f"{PARENT}/bindings/{BINDING_ID}"
AUTH_PROVIDER_NAME = f"{PARENT}/authProviders/finserv-ledger-api-key"


def get_oauth_token() -> str:
    """Retrieve Google Cloud OAuth2 Access Token."""
    try:
        return subprocess.check_output(
            ["gcloud", "auth", "application-default", "print-access-token"],
            stderr=subprocess.PIPE
        ).decode().strip()
    except Exception as e:
        console.print(f"[bold red]Failed to get access token:[/bold red] {e}")
        sys.exit(1)


def call_registry_mcp(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a JSON-RPC 2.0 call against Google Cloud Agent Registry MCP Server."""
    token = get_oauth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    body = {
        "jsonrpc": "2.0",
        "id": int(time.time()),
        "method": method
    }
    if params:
        body["params"] = params

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(AGENT_REGISTRY_MCP_URL, json=body, headers=headers)
        if resp.status_code != 200:
            console.print(f"[bold red]HTTP {resp.status_code} Error from Agent Registry:[/bold red] {resp.text}")
            sys.exit(1)
        res_json = resp.json()
        if "error" in res_json:
            console.print(f"[bold red]Agent Registry JSON-RPC Error:[/bold red] {json.dumps(res_json['error'], indent=2)}")
            sys.exit(1)
        return res_json.get("result", {})


def explain_onboarding_paths():
    """Pillar 1: Explain the 3 Onboarding Paths to bring tools into Google Cloud Tool Registry."""
    console.print(Panel(
        "[bold cyan]Tool Registry: How to Bring in Tools (All 3 Onboarding Paths)[/bold cyan]\n"
        "Google Cloud Agent Registry provides 3 unified paths for enterprise tool management at scale.",
        title="Pillar 1: Tool Registry Onboarding",
        border_style="cyan"
    ))

    table = Table(title="The 3 Onboarding Paths in Google Cloud Tool Registry", show_header=True, header_style="bold magenta")
    table.add_column("Onboarding Path", style="bold green", width=22)
    table.add_column("Mechanism & Implementation", style="white", width=42)
    table.add_column("Enterprise Advantage", style="yellow", width=36)

    table.add_row(
        "Path 1: 1P Google Cloud\nMCP Auto-Discovery",
        "Enable native GCP APIs (BigQuery, Spanner, Vertex AI, Cloud Storage).\nAgent Registry automatically discovers & catalogs 1P MCP servers in the mcpServers directory.",
        "Zero setup; zero infrastructure maintenance; enterprise IAM role mapping out-of-the-box."
    )
    table.add_row(
        "Path 2: Compute\nAuto-Discovery\n(Cloud Run & GKE)",
        "Cloud Run:\n  Deploy with --functional-type=mcp-server\n  or label registry.cloud.google.com/functional-type=mcp-server.\nGKE:\n  Annotate Pods with registry.gke.io/functional-type: \"MCP_SERVER\".",
        "Continuous automated discovery of microservices as soon as developers deploy code."
    )
    table.add_row(
        "Path 3: Declarative Custom\n& 3P ToolSpec Onboarding",
        "Declarative ToolSpec JSON schema (toolspec.json) onboarded via Agent Registry MCP create_service or gcloud beta agent-registry services create.",
        "Governance control over 3P APIs, SaaS endpoints, legacy databases, and custom agents."
    )

    console.print(table)
    console.print("[dim]Use './deploy_cloud_run_mcp.sh' to demonstrate Path 2 and 'toolspec.json' for Path 3.[/dim]\n")


def list_meta_tools():
    """Pillar 2: Discover built-in governance tools available on Agent Registry Remote MCP Server."""
    console.print(Panel(
        f"[bold cyan]Querying Google Cloud Agent Registry Remote MCP Server[/bold cyan]\n"
        f"Gateway: [bold white]{AGENT_REGISTRY_MCP_URL}[/bold white]\n"
        f"Project: [bold yellow]{PROJECT_ID}[/bold yellow] | Location: [bold yellow]{REGION}[/bold yellow]",
        title="Agent Registry Meta-Tool Discovery",
        border_style="cyan"
    ))

    result = call_registry_mcp("tools/list")
    tools = result.get("tools", [])

    table = Table(title="Google Cloud Agent Registry Governance Meta-Tools", show_header=True, header_style="bold magenta")
    table.add_column("Meta-Tool Name", style="bold green")
    table.add_column("Description", style="white")

    for t in tools:
        table.add_row(t.get("name", ""), t.get("description", "").strip())

    console.print(table)
    console.print(f"[bold green]✓ Discovered {len(tools)} governance tools hosted natively by Agent Registry.[/bold green]\n")


def poll_search_for_endpoint(expected_url_substr: Optional[str], max_wait: int = 15) -> bool:
    """Poll search_mcp_servers until the expected endpoint is indexed."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            res = call_registry_mcp("tools/call", {
                "name": "search_mcp_servers",
                "arguments": {"parent": PARENT, "searchString": "ledger"}
            })
            content_raw = res.get("content", [{}])[0].get("text", "{}")
            data = json.loads(content_raw)
            servers = data.get("mcpServers", [])
            if expected_url_substr is None:
                if len(servers) == 0:
                    return True
            else:
                if servers:
                    urls = [i.get("url", "") for i in servers[0].get("interfaces", [])]
                    if any(expected_url_substr in u for u in urls):
                        return True
        except Exception:
            pass
        time.sleep(1)
    return False


def load_toolspec() -> Dict[str, Any]:
    """Load declarative ToolSpec definition from toolspec.json (Path 3 Onboarding)."""
    toolspec_path = os.path.join(os.path.dirname(__file__), "toolspec.json")
    if os.path.exists(toolspec_path):
        try:
            with open(toolspec_path, "r") as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse toolspec.json ({e}), using default.[/yellow]")

    return {
        "type": "TOOL_SPEC",
        "content": {
            "tools": [
                {
                    "name": "verify_ledger_transaction",
                    "description": "Verifies financial ledger transactions, audit timestamps, and cryptographic signature validity across FinServ core ledgers.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "transaction_id": {
                                "type": "string",
                                "description": "The transaction identifier to verify (e.g. TX-9941)"
                            }
                        },
                        "required": ["transaction_id"]
                    }
                }
            ]
        }
    }


def register_v1():
    """Register Source Agent, FinServ Ledger MCP Server (v1 via toolspec.json), and Outbound Binding."""
    console.print(Panel(
        f"[bold blue]Registering Enterprise Agent, MCP Tool, and Outbound Binding[/bold blue]\n"
        f"Parent: [white]{PARENT}[/white]\n"
        f"Source Agent: [bold yellow]{SOURCE_AGENT_ID}[/bold yellow] ({SOURCE_AGENT_URN})\n"
        f"Target Tool: [bold yellow]{SERVICE_ID}[/bold yellow] -> [bold green]{LEDGER_V1_URL}[/bold green]\n"
        f"Outbound Binding: [bold cyan]{BINDING_ID}[/bold cyan]\n"
        f"Auth Provider: [bold magenta]{AUTH_PROVIDER_NAME}[/bold magenta]\n"
        f"Onboarding Mode: [bold green]Path 3 (Declarative toolspec.json)[/bold green]",
        title="SecOps Tool & Outbound Binding Onboarding",
        border_style="blue"
    ))

    # 1. Ensure Source Agent Service is registered
    services_res = call_registry_mcp("tools/call", {
        "name": "list_services",
        "arguments": {"parent": PARENT}
    })
    content_raw = services_res.get("content", [{}])[0].get("text", "{}")
    existing_services = json.loads(content_raw).get("services", [])
    agent_exists = any(s.get("name") == SOURCE_AGENT_RESOURCE_NAME for s in existing_services)

    if not agent_exists:
        console.print("[dim]Registering Source Agent in Agent Registry...[/dim]")
        agent_args = {
            "parent": PARENT,
            "serviceId": SOURCE_AGENT_ID,
            "service": {
                "displayName": "FinServ Auditor Autonomous Agent",
                "description": "SecOps-approved FinServ financial compliance auditor agent",
                "interfaces": [
                    {
                        "url": f"https://{SOURCE_AGENT_ID}-{PROJECT_NUMBER}.{REGION}.run.app/agent",
                        "protocolBinding": "JSONRPC"
                    }
                ],
                "agentSpec": {
                    "type": "NO_SPEC"
                }
            }
        }
        call_registry_mcp("tools/call", {"name": "create_service", "arguments": agent_args})
        console.print(f"[bold green]✓ Registered Source Agent: {SOURCE_AGENT_ID}[/bold green]")
    else:
        console.print(f"[green]✓ Source Agent {SOURCE_AGENT_ID} already registered.[/green]")

    # 2. Ensure FinServ Ledger MCP Service is registered pointing to v1 using toolspec.json
    toolspec_data = load_toolspec()
    tool_exists = any(s.get("name") == SERVICE_RESOURCE_NAME for s in existing_services)

    if not tool_exists:
        console.print("[dim]Creating FinServ Ledger MCP Service via Declarative ToolSpec (Path 3)...[/dim]")
        tool_args = {
            "parent": PARENT,
            "serviceId": SERVICE_ID,
            "service": {
                "displayName": toolspec_data.get("displayName", "FinServ Production Ledger MCP"),
                "description": "Admin-approved MCP server for verifying ledger transactions and audit trails (v1.0-LEGACY)",
                "interfaces": [
                    {
                        "url": LEDGER_V1_URL,
                        "protocolBinding": "JSONRPC"
                    }
                ],
                "mcpServerSpec": toolspec_data.get("mcpServerSpec", toolspec_data)
            }
        }
        call_registry_mcp("tools/call", {"name": "create_service", "arguments": tool_args})
    else:
        console.print("[yellow]Updating target tool endpoint to v1.0...[/yellow]")
        tool_args = {
            "service": {
                "name": SERVICE_RESOURCE_NAME,
                "description": "Admin-approved MCP server for verifying ledger transactions and audit trails (v1.0-LEGACY)",
                "interfaces": [
                    {
                        "url": LEDGER_V1_URL,
                        "protocolBinding": "JSONRPC"
                    }
                ]
            },
            "updateMask": "interfaces,description"
        }
        call_registry_mcp("tools/call", {"name": "update_service", "arguments": tool_args})

    # 3. Ensure Outbound Binding is created linking Source Agent -> Target Tool + AuthProvider
    bindings_res = call_registry_mcp("tools/call", {
        "name": "list_bindings",
        "arguments": {"parent": PARENT}
    })
    b_content_raw = bindings_res.get("content", [{}])[0].get("text", "{}")
    existing_bindings = json.loads(b_content_raw).get("bindings", [])
    binding_exists = any(
        b.get("name") == BINDING_RESOURCE_NAME or
        b.get("name") == f"projects/{PROJECT_NUMBER}/locations/{REGION}/bindings/{BINDING_ID}"
        for b in existing_bindings
    )

    if not binding_exists:
        console.print("[dim]Calling create_binding on Agent Registry Remote MCP Server...[/dim]")
        # We bind source.identifier to SOURCE_AGENT_URN and target.identifier to TARGET_TOOL_URN
        binding_args = {
            "parent": PARENT,
            "bindingId": BINDING_ID,
            "binding": {
                "name": BINDING_RESOURCE_NAME,
                "displayName": "FinServ Auditor Outbound Binding",
                "description": "Admin-approved Outbound Binding linking FinServ Auditor Agent to FinServ Ledger MCP Server with managed auth",
                "source": {
                    "identifier": SOURCE_AGENT_URN
                },
                "target": {
                    "identifier": TARGET_TOOL_URN
                },
                "authProviderBinding": {
                    "authProvider": AUTH_PROVIDER_NAME
                }
            }
        }
        try:
            call_registry_mcp("tools/call", {"name": "create_binding", "arguments": binding_args})
            console.print(f"[bold green]✓ Created Outbound Binding: {BINDING_ID}[/bold green]")
        except Exception as e:
            # Fallback with canonical URN if short URN is rejected by backend version
            console.print(f"[yellow]Retrying with canonical URN format: {e}[/yellow]")
            binding_args["binding"]["source"]["identifier"] = CANONICAL_SOURCE_AGENT_URN
            binding_args["binding"]["target"]["identifier"] = CANONICAL_TARGET_TOOL_URN
            call_registry_mcp("tools/call", {"name": "create_binding", "arguments": binding_args})
            console.print(f"[bold green]✓ Created Outbound Binding (Canonical URN): {BINDING_ID}[/bold green]")
    else:
        console.print(f"[green]✓ Outbound Binding {BINDING_ID} is already active.[/green]")

    poll_search_for_endpoint("ledger-mcp-v1", max_wait=15)
    console.print(f"[bold green]✓ Successfully onboarded {SERVICE_ID} (v1.0) with Outbound Binding![/bold green]\n")


def inspect_bindings():
    """Pillar 3: Enumerate and fetch Outbound Bindings via Agent Registry Remote MCP Server."""
    console.print(Panel(
        f"[bold cyan]Inspecting Active Enterprise Outbound Bindings[/bold cyan]\n"
        f"Registry Gateway: [bold white]{AGENT_REGISTRY_MCP_URL}[/bold white]\n"
        f"Parent: [white]{PARENT}[/white]\n"
        f"Source Filter: [yellow]{SOURCE_AGENT_URN}[/yellow] (or canonical)\n"
        f"Target Filter: [yellow]{TARGET_TOOL_URN}[/yellow]",
        title="Agent Registry Outbound Governance Inspection",
        border_style="cyan"
    ))

    # Fetch available bindings for our source agent
    fetch_res = call_registry_mcp("tools/call", {
        "name": "fetch_available_bindings",
        "arguments": {
            "parent": PARENT,
            "sourceIdentifier": SOURCE_AGENT_URN
        }
    })
    raw_fetch = fetch_res.get("content", [{}])[0].get("text", "{}")
    bindings = json.loads(raw_fetch).get("bindings", [])

    # If empty, check canonical URN
    if not bindings:
        fetch_res_canon = call_registry_mcp("tools/call", {
            "name": "fetch_available_bindings",
            "arguments": {
                "parent": PARENT,
                "sourceIdentifier": CANONICAL_SOURCE_AGENT_URN
            }
        })
        raw_canon = fetch_res_canon.get("content", [{}])[0].get("text", "{}")
        bindings = json.loads(raw_canon).get("bindings", [])

    if not bindings:
        console.print("[bold red]No approved Outbound Bindings found for this source agent.[/bold red]\n")
        return

    table = Table(title=f"Active Outbound Tool Bindings ({len(bindings)} active)", show_header=True, header_style="bold green")
    table.add_column("Binding Resource", style="bold white")
    table.add_column("Source Agent URN", style="cyan")
    table.add_column("Target Tool URN", style="yellow")
    table.add_column("Managed Auth Provider", style="magenta")
    table.add_column("Governance Status", style="bold green")

    for b in bindings:
        name = b.get("name", "").split("/")[-1]
        src = b.get("source", {}).get("identifier", "N/A")
        tgt = b.get("target", {}).get("identifier", "N/A")
        auth = b.get("authProviderBinding", {}).get("authProvider", "None").split("/")[-1]
        table.add_row(name, src, tgt, auth, "APPROVED & BOUND")

    console.print(table)
    console.print(f"[bold green]✓ Verified {len(bindings)} active Outbound Binding(s). Autonomous Agent is authorized to invoke bound MCP tools.[/bold green]\n")


def search_tool(term: str = "ledger"):
    """Search registered MCP servers via Agent Registry search_mcp_servers tool."""
    console.print(Panel(
        f"[bold cyan]Executing Runtime Tool Discovery[/bold cyan]\n"
        f"Search Term: [bold yellow]\"{term}\"[/bold yellow]\n"
        f"Parent: [white]{PARENT}[/white]",
        title="Agent Registry Tool Discovery",
        border_style="cyan"
    ))

    res = call_registry_mcp("tools/call", {
        "name": "search_mcp_servers",
        "arguments": {
            "parent": PARENT,
            "searchString": term
        }
    })

    content_raw = res.get("content", [{}])[0].get("text", "{}")
    data = json.loads(content_raw)
    servers = data.get("mcpServers", [])

    if not servers:
        console.print(f"[bold red]No approved MCP servers found matching \"{term}\".[/bold red]")
        return None

    table = Table(title=f"Discovered Approved MCP Tool Endpoints ({len(servers)} found)", show_header=True, header_style="bold cyan")
    table.add_column("Display Name", style="bold white")
    table.add_column("Exposed MCP URL", style="bold green")
    table.add_column("Tools", style="yellow")
    table.add_column("Description", style="white")

    for s in servers:
        name = s.get("displayName", "N/A")
        urls = ", ".join(i.get("url", "") for i in s.get("interfaces", []))
        tools = ", ".join(t.get("name", "") for t in s.get("tools", []))
        desc = s.get("description", "")
        table.add_row(name, urls, tools, desc)

    console.print(table)
    return servers[0]


def cutover_v2():
    """Zero-downtime cutover: update service interfaces[0].url to v2."""
    console.print(Panel(
        f"[bold magenta]Initiating Zero-Downtime Governance Cutover[/bold magenta]\n"
        f"Target Service: [white]{SERVICE_RESOURCE_NAME}[/white]\n"
        f"Promoting New Version: [bold green]v2.0-ZERO-TRUST-HARDENED[/bold green]\n"
        f"New Endpoint: [bold cyan]{LEDGER_V2_URL}[/bold cyan]\n"
        f"Outbound Binding: [bold white]Preserved ({BINDING_ID})[/bold white]\n"
        f"Zero Client Code Changes Required!",
        title="Admin Zero-Downtime Tool Migration",
        border_style="magenta"
    ))

    args = {
        "service": {
            "name": SERVICE_RESOURCE_NAME,
            "description": "SecOps-approved MCP server for verifying ledger transactions (Cutover to v2 Zero-Trust Hardened with ML-DSA Post-Quantum Signatures)",
            "interfaces": [
                {
                    "url": LEDGER_V2_URL,
                    "protocolBinding": "JSONRPC"
                }
            ]
        },
        "updateMask": "interfaces,description"
    }

    call_registry_mcp("tools/call", {"name": "update_service", "arguments": args})
    poll_search_for_endpoint("ledger-mcp-v2", max_wait=15)
    console.print(f"[bold green]✓ Cutover complete! Central registry now directs all autonomous agents to v2.0.[/bold green]\n")


def revoke():
    """Instant tool & binding revocation: delete binding and service to block agent access."""
    console.print(Panel(
        f"[bold red]CRITICAL: Instant Security Tool & Binding Revocation[/bold red]\n"
        f"Target Binding: [white]{BINDING_RESOURCE_NAME}[/white]\n"
        f"Target Service: [white]{SERVICE_RESOURCE_NAME}[/white]\n"
        f"Reason: SecOps Emergency Quarantine / Rogue Tool Disablement",
        title="Emergency Governance Kill Switch",
        border_style="red"
    ))

    # 1. Delete Outbound Binding
    console.print("[dim]Deleting Outbound Binding via Agent Registry MCP delete_binding...[/dim]")
    try:
        call_registry_mcp("tools/call", {
            "name": "delete_binding",
            "arguments": {"name": BINDING_RESOURCE_NAME}
        })
        console.print(f"[bold green]✓ Deleted Outbound Binding: {BINDING_ID}[/bold green]")
    except Exception as e:
        console.print(f"[yellow]Binding deletion note: {e}[/yellow]")

    # 2. Delete Service
    console.print("[dim]Deleting Tool Service via Agent Registry MCP delete_service...[/dim]")
    try:
        call_registry_mcp("tools/call", {
            "name": "delete_service",
            "arguments": {"name": SERVICE_RESOURCE_NAME}
        })
        console.print(f"[bold green]✓ Deleted Service: {SERVICE_ID}[/bold green]")
    except Exception as e:
        console.print(f"[yellow]Service deletion note: {e}[/yellow]")

    poll_search_for_endpoint(None, max_wait=15)
    console.print(f"[bold green]✓ Revocation complete. Tool and Outbound Binding deleted from Agent Registry.[/bold green]\n")


def main():
    parser = argparse.ArgumentParser(description="Google Cloud Agent Registry MCP Control Plane")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("explain-paths", help="Explain all 3 Tool Registry onboarding paths (Pillar 1)")
    subparsers.add_parser("list-meta-tools", help="Enumerate built-in Agent Registry governance tools (Pillar 2)")
    subparsers.add_parser("register-v1", help="Register Finserv Ledger MCP v1 (Path 3 ToolSpec) and Outbound Binding")
    subparsers.add_parser("inspect-bindings", help="Inspect active Outbound Bindings (Pillar 3)")
    subparsers.add_parser("list-bindings", help="Alias for inspect-bindings")
    subparsers.add_parser("fetch-bindings", help="Alias for inspect-bindings")
    search_p = subparsers.add_parser("search", help="Search approved MCP servers")
    search_p.add_argument("--term", default="ledger", help="Search query term")
    subparsers.add_parser("cutover-v2", help="Cutover tool definition to v2.0 (Pillar 5)")
    subparsers.add_parser("revoke", help="Emergency revocation of registered tool & outbound binding (Kill-Switch)")

    args = parser.parse_args()

    if args.subcommand == "explain-paths":
        explain_onboarding_paths()
    elif args.subcommand == "list-meta-tools":
        list_meta_tools()
    elif args.subcommand == "register-v1":
        register_v1()
    elif args.subcommand in ("inspect-bindings", "list-bindings", "fetch-bindings"):
        inspect_bindings()
    elif args.subcommand == "search":
        search_tool(args.term)
    elif args.subcommand == "cutover-v2":
        cutover_v2()
    elif args.subcommand == "revoke":
        revoke()


if __name__ == "__main__":
    main()
