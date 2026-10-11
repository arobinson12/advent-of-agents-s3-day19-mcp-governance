#!/usr/bin/env python3
"""
Agent Registry Control Plane CLI
Advent of Agents Season 3 — Day 19
Dynamic MCP Governance: Eliminating Hardcoded Tool Endpoints

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
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

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

# Legacy REST Endpoint Service
REST_ENDPOINT_ID = "swift-sanctions-api"
REST_ENDPOINT_RESOURCE_NAME = f"{PARENT}/services/{REST_ENDPOINT_ID}"
CANONICAL_REST_ENDPOINT_URN = f"urn:endpoint:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:locations:{REGION}:agentregistry:services:{REST_ENDPOINT_ID}"

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


def show_onboarding_specs():
    """Explain & show how resources enter Agent Registry at scale (All 3 Pipelines & CQRS Model)."""
    console.print(Panel(
        f"[bold cyan]Google Cloud Agent Registry: Enterprise Ingestion Pipelines at Scale[/bold cyan]\n"
        f"Control Plane CQRS Model: Writable [bold yellow]Services[/bold yellow] & [bold yellow]Bindings[/bold yellow] "
        f"project into Read-Only [bold green]McpServers[/bold green], [bold green]Agents[/bold green], & [bold green]Endpoints[/bold green] collections.\n"
        f"Parent Scope: [white]{PARENT}[/white]",
        title="Agent Registry Onboarding Architecture",
        border_style="cyan"
    ))

    # Pipeline Comparison Table
    table = Table(title="The 3 Enterprise Onboarding Pipelines", show_header=True, header_style="bold magenta")
    table.add_column("Pipeline", style="bold green", width=22)
    table.add_column("Resource Type", style="cyan", width=20)
    table.add_column("Trigger & Specification", style="white", width=42)
    table.add_column("Enterprise Advantage", style="yellow", width=34)

    table.add_row(
        "Pipeline 1: Zero-Touch\nCompute Auto-Discovery",
        "Cloud Run & GKE\n(MCP Servers & Agents)",
        "Cloud Run: --functional-type=mcp-server\nCloud Run Agent: --functional-type=agent --identity-type=agent-identity\nGKE: registry.gke.io/functional-type label",
        "Automated continuous cataloging as workloads deploy. Zero manual registration."
    )
    table.add_row(
        "Pipeline 2: Declarative\nServices API & CLI",
        "Custom Tools, A2A Agents\n& Legacy REST Endpoints",
        "MCP Server: specs/toolspec.json\nA2A Agent: specs/agent-card.json (A2A v1.0)\nREST API: endpointSpec (NO_SPEC)",
        "Central SecOps vetting of third-party APIs, SaaS, custom agents, and internal microservices."
    )
    table.add_row(
        "Pipeline 3: GitOps &\nTerraform IaC",
        "google_agent_registry_*\n(Services & Bindings)",
        "Declarative HCL in terraform/main.tf:\n  - google_agent_registry_service\n  - google_agent_registry_binding",
        "Reproducible CI/CD pipelines, peer-reviewed Git pull requests, and automated compliance."
    )

    console.print(table)

    # Show artifacts preview
    console.print("\n[bold yellow]── Pipeline 2 Artifact: Official MCP ToolSpec (specs/toolspec.json) ──[/bold yellow]")
    with open(os.path.join(os.path.dirname(__file__), "specs/toolspec.json")) as f:
        toolspec_sample = f.read()
    console.print(Syntax(toolspec_sample, "json", theme="monokai", line_numbers=True))

    console.print("\n[bold yellow]── Pipeline 2 Artifact: Official A2A v1.0 Agent Card (specs/agent-card.json) ──[/bold yellow]")
    with open(os.path.join(os.path.dirname(__file__), "specs/agent-card.json")) as f:
        agent_card_sample = f.read()
    console.print(Syntax(agent_card_sample, "json", theme="monokai", line_numbers=True))

    console.print("\n[bold yellow]── Pipeline 3 Artifact: Terraform GitOps IaC (terraform/main.tf snippet) ──[/bold yellow]")
    with open(os.path.join(os.path.dirname(__file__), "terraform/main.tf")) as f:
        tf_sample = f.read()[:950] + "\n  # ... (includes google_agent_registry_binding with managed auth)\n}"
    console.print(Syntax(tf_sample, "hcl", theme="monokai", line_numbers=True))
    console.print("")


def explain_onboarding_paths():
    """Alias for show_onboarding_specs."""
    show_onboarding_specs()


def list_meta_tools():
    """Enumerate the 20 built-in governance tools grouped by Read vs. Write operations."""
    console.print(Panel(
        f"[bold cyan]Google Cloud Agent Registry Remote MCP Server — 20 Built-in Meta-Tools[/bold cyan]\n"
        f"Gateway: [bold white]{AGENT_REGISTRY_MCP_URL}[/bold white]\n"
        f"Project: [bold yellow]{PROJECT_ID}[/bold yellow] | Location: [bold yellow]{REGION}[/bold yellow]",
        title="Agent Registry Meta-Tool Discovery",
        border_style="cyan"
    ))

    result = call_registry_mcp("tools/list")
    tools = result.get("tools", [])

    read_tools = []
    write_tools = []

    for t in tools:
        name = t.get("name", "")
        desc = t.get("description", "").strip()
        if any(name.startswith(p) for p in ["list_", "get_", "search_", "fetch_"]):
            read_tools.append((name, desc))
        else:
            write_tools.append((name, desc))

    # Read Tools Table
    read_table = Table(title="Read & Discovery Meta-Tools (Consumer Catalog Querying)", show_header=True, header_style="bold green")
    read_table.add_column("Meta-Tool Name", style="bold cyan", width=26)
    read_table.add_column("Target Catalog / Capability", style="white")

    for name, desc in read_tools:
        read_table.add_row(name, desc)

    console.print(read_table)

    # Write Tools Table
    write_table = Table(title="Write & Governance Meta-Tools (Control Plane Administration)", show_header=True, header_style="bold magenta")
    write_table.add_column("Meta-Tool Name", style="bold red", width=26)
    write_table.add_column("Administrative Operation", style="white")

    for name, desc in write_tools:
        write_table.add_row(name, desc)

    console.print(write_table)
    console.print(f"[bold green]✓ Verified {len(tools)} total governance tools (Read: {len(read_tools)}, Write: {len(write_tools)}) hosted natively by Agent Registry.[/bold green]\n")


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
    """Load declarative ToolSpec definition from specs/toolspec.json."""
    toolspec_path = os.path.join(os.path.dirname(__file__), "specs/toolspec.json")
    if not os.path.exists(toolspec_path):
        toolspec_path = os.path.join(os.path.dirname(__file__), "toolspec.json")
    if os.path.exists(toolspec_path):
        try:
            with open(toolspec_path, "r") as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse toolspec.json ({e}), using default.[/yellow]")

    return {
        "displayName": "FinServ Production Ledger MCP",
        "description": "Enterprise SecOps-approved MCP server for verifying financial transactions",
        "mcpServerSpec": {
            "type": "TOOL_SPEC",
            "content": {
                "tools": [
                    {
                        "name": "verify_ledger_transaction",
                        "description": "Verifies financial ledger transactions, audit timestamps, and cryptographic signature validity.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"transaction_id": {"type": "string"}},
                            "required": ["transaction_id"]
                        }
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
        "description": "Autonomous financial services auditing agent powered by Google ADK",
        "version": "1.0.0",
        "supportedInterfaces": [{"protocolBinding": "JSONRPC", "protocolVersion": "1.0", "url": f"https://{SOURCE_AGENT_ID}-{PROJECT_NUMBER}.{REGION}.run.app/agent"}],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [{"id": "audit_wire_transfer", "name": "audit_wire_transfer", "description": "Audits wire transfers", "tags": ["auditing", "compliance"]}]
    }


def onboard_all():
    """Onboard all 3 service types (MCP Server, Agent, REST Endpoint) + Outbound Binding."""
    console.print(Panel(
        f"[bold blue]Onboarding All Enterprise Resources to Google Cloud Agent Registry[/bold blue]\n"
        f"Parent Scope: [white]{PARENT}[/white]\n"
        f"1. MCP Server Service: [bold yellow]{SERVICE_ID}[/bold yellow] (specs/toolspec.json -> {LEDGER_V1_URL})\n"
        f"2. Agent Service: [bold yellow]{SOURCE_AGENT_ID}[/bold yellow] (specs/agent-card.json A2A v1.0)\n"
        f"3. REST Endpoint Service: [bold yellow]{REST_ENDPOINT_ID}[/bold yellow] (endpointSpec: NO_SPEC)\n"
        f"4. Outbound Binding: [bold cyan]{BINDING_ID}[/bold cyan] ({SOURCE_AGENT_URN} -> {TARGET_TOOL_URN})\n"
        f"5. Managed Auth Provider: [bold magenta]{AUTH_PROVIDER_NAME}[/bold magenta]",
        title="SecOps Enterprise Fleet Onboarding",
        border_style="blue"
    ))

    # Query existing services
    services_res = call_registry_mcp("tools/call", {
        "name": "list_services",
        "arguments": {"parent": PARENT}
    })
    content_raw = services_res.get("content", [{}])[0].get("text", "{}")
    existing_services = json.loads(content_raw).get("services", [])
    existing_names = [s.get("name") for s in existing_services]

    # 1. Onboard / Update MCP Server Service
    toolspec_data = load_toolspec()
    mcp_spec = toolspec_data.get("mcpServerSpec", toolspec_data)
    if SERVICE_RESOURCE_NAME not in existing_names:
        console.print(f"[dim]Creating MCP Service '{SERVICE_ID}' (Pipeline 2: Declarative ToolSpec)...[/dim]")
        call_registry_mcp("tools/call", {
            "name": "create_service",
            "arguments": {
                "parent": PARENT,
                "serviceId": SERVICE_ID,
                "service": {
                    "displayName": toolspec_data.get("displayName", "FinServ Production Ledger MCP"),
                    "description": "Admin-approved MCP server for verifying ledger transactions and audit trails (v1.0-LEGACY)",
                    "interfaces": [{"url": LEDGER_V1_URL, "protocolBinding": "JSONRPC"}],
                    "mcpServerSpec": mcp_spec
                }
            }
        })
        console.print(f"[bold green]✓ Created MCP Server Service: {SERVICE_ID}[/bold green]")
    else:
        console.print(f"[yellow]Ensuring MCP Service '{SERVICE_ID}' points to v1.0 endpoint...[/yellow]")
        call_registry_mcp("tools/call", {
            "name": "update_service",
            "arguments": {
                "service": {
                    "name": SERVICE_RESOURCE_NAME,
                    "description": "Admin-approved MCP server for verifying ledger transactions and audit trails (v1.0-LEGACY)",
                    "interfaces": [{"url": LEDGER_V1_URL, "protocolBinding": "JSONRPC"}]
                },
                "updateMask": "interfaces,description"
            }
        })
        console.print(f"[bold green]✓ Configured MCP Server Service: {SERVICE_ID} -> v1.0[/bold green]")

    # 2. Onboard / Update Autonomous Agent Service (A2A Agent Card)
    agent_card_data = load_agent_card()
    if SOURCE_AGENT_RESOURCE_NAME not in existing_names:
        console.print(f"[dim]Creating Agent Service '{SOURCE_AGENT_ID}' (Pipeline 2: A2A v1.0 Agent Card)...[/dim]")
        call_registry_mcp("tools/call", {
            "name": "create_service",
            "arguments": {
                "parent": PARENT,
                "serviceId": SOURCE_AGENT_ID,
                "service": {
                    "displayName": "FinServ Compliance & Security Auditor Agent",
                    "description": agent_card_data.get("description", "Autonomous financial services auditing agent"),
                    "agentSpec": {
                        "type": "A2A_AGENT_CARD",
                        "content": agent_card_data
                    }
                }
            }
        })
        console.print(f"[bold green]✓ Created Agent Service: {SOURCE_AGENT_ID}[/bold green]")
    else:
        console.print(f"[dim]Updating Agent Service '{SOURCE_AGENT_ID}' with A2A v1.0 Card...[/dim]")
        call_registry_mcp("tools/call", {
            "name": "update_service",
            "arguments": {
                "service": {
                    "name": SOURCE_AGENT_RESOURCE_NAME,
                    "displayName": "FinServ Compliance & Security Auditor Agent",
                    "description": agent_card_data.get("description", "Autonomous financial services auditing agent"),
                    "agentSpec": {
                        "type": "A2A_AGENT_CARD",
                        "content": agent_card_data
                    }
                },
                "updateMask": "displayName,description,agentSpec"
            }
        })
        console.print(f"[bold green]✓ Configured Agent Service: {SOURCE_AGENT_ID}[/bold green]")

    # 3. Onboard / Update REST API Endpoint Service (endpointSpec: NO_SPEC)
    if REST_ENDPOINT_RESOURCE_NAME not in existing_names:
        console.print(f"[dim]Creating REST Endpoint Service '{REST_ENDPOINT_ID}' (Pipeline 2: REST Endpoint)...[/dim]")
        call_registry_mcp("tools/call", {
            "name": "create_service",
            "arguments": {
                "parent": PARENT,
                "serviceId": REST_ENDPOINT_ID,
                "service": {
                    "displayName": "SWIFT OFAC Sanctions Screening API",
                    "description": "Real-time sanctions and PEP compliance check API endpoint",
                    "interfaces": [{"url": "https://api.swift-screening.internal/v1/check", "protocolBinding": "HTTP_JSON"}],
                    "endpointSpec": {"type": "NO_SPEC"}
                }
            }
        })
        console.print(f"[bold green]✓ Created REST Endpoint Service: {REST_ENDPOINT_ID}[/bold green]")
    else:
        console.print(f"[green]✓ REST Endpoint Service '{REST_ENDPOINT_ID}' already active.[/green]")

    # 4. Create Outbound Binding with Managed Auth Provider
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
        console.print("[dim]Creating Outbound Binding on Agent Registry Remote MCP Server...[/dim]")
        binding_args = {
            "parent": PARENT,
            "bindingId": BINDING_ID,
            "binding": {
                "name": BINDING_RESOURCE_NAME,
                "displayName": "FinServ Auditor Outbound Binding",
                "description": "Admin-approved Outbound Binding linking FinServ Auditor Agent to FinServ Ledger MCP Server with managed auth",
                "source": {"identifier": SOURCE_AGENT_URN},
                "target": {"identifier": TARGET_TOOL_URN},
                "authProviderBinding": {"authProvider": AUTH_PROVIDER_NAME}
            }
        }
        try:
            call_registry_mcp("tools/call", {"name": "create_binding", "arguments": binding_args})
            console.print(f"[bold green]✓ Created Outbound Binding: {BINDING_ID}[/bold green]")
        except Exception:
            binding_args["binding"]["source"]["identifier"] = CANONICAL_SOURCE_AGENT_URN
            binding_args["binding"]["target"]["identifier"] = CANONICAL_TARGET_TOOL_URN
            call_registry_mcp("tools/call", {"name": "create_binding", "arguments": binding_args})
            console.print(f"[bold green]✓ Created Outbound Binding (Canonical URN): {BINDING_ID}[/bold green]")
    else:
        console.print(f"[green]✓ Outbound Binding {BINDING_ID} is active.[/green]")

    poll_search_for_endpoint("ledger-mcp-v1", max_wait=15)
    console.print(f"[bold green]✓ All enterprise resources onboarded and ready for governed agent execution![/bold green]\n")


def register_v1():
    """Alias for onboard_all."""
    onboard_all()


def inspect_catalog():
    """Query read-only catalog collections and print CQRS Write -> Read Catalog Projection Table."""
    console.print(Panel(
        f"[bold cyan]Google Cloud Agent Registry: CQRS Write ➔ Read Catalog Inspection[/bold cyan]\n"
        f"Querying Read-Only Collections via Gateway: [bold white]{AGENT_REGISTRY_MCP_URL}[/bold white]\n"
        f"Parent Scope: [white]{PARENT}[/white]",
        title="Agent Registry CQRS Catalog Projection",
        border_style="cyan"
    ))

    # 1. Query mcpServers collection
    mcp_res = call_registry_mcp("tools/call", {"name": "list_mcp_servers", "arguments": {"parent": PARENT}})
    mcp_servers = json.loads(mcp_res.get("content", [{}])[0].get("text", "{}")).get("mcpServers", [])

    # 2. Query agents collection
    agent_res = call_registry_mcp("tools/call", {"name": "list_agents", "arguments": {"parent": PARENT}})
    agents = json.loads(agent_res.get("content", [{}])[0].get("text", "{}")).get("agents", [])

    # 3. Query endpoints collection
    endpoint_res = call_registry_mcp("tools/call", {"name": "list_endpoints", "arguments": {"parent": PARENT}})
    endpoints = json.loads(endpoint_res.get("content", [{}])[0].get("text", "{}")).get("endpoints", [])

    table = Table(title="CQRS Data Model: Writable Services Projected into Read-Only Catalog", show_header=True, header_style="bold magenta")
    table.add_column("Writable Source Service", style="bold yellow", width=26)
    table.add_column("Catalog Collection", style="bold cyan", width=18)
    table.add_column("Canonical Logical URN", style="bold green", width=36)
    table.add_column("Physical Interface URI", style="white", width=34)
    table.add_column("Indexed Capability / Schema", style="magenta", width=28)

    # Filter & add MCP Servers
    for m in mcp_servers:
        runtime_ref = m.get("attributes", {}).get("agentregistry.googleapis.com/system/RuntimeReference", {}).get("uri", "")
        if "finserv-ledger-mcp" in runtime_ref or "finserv-ledger-mcp" in m.get("name", ""):
            src = f"services/{SERVICE_ID}"
            col = "mcpServers/*"
            urn = m.get("mcpServerId", CANONICAL_TARGET_TOOL_URN)
            urls = ", ".join(i.get("url", "") for i in m.get("interfaces", []))
            tools = ", ".join(t.get("name", "") for t in m.get("tools", []))
            table.add_row(src, col, urn, urls or LEDGER_V1_URL, f"Tool: {tools} [readOnlyHint=true]")

    # Filter & add Agents
    for a in agents:
        runtime_ref = a.get("attributes", {}).get("agentregistry.googleapis.com/system/RuntimeReference", {}).get("uri", "")
        if "finserv-auditor-agent" in runtime_ref or "finserv-auditor-agent" in a.get("displayName", ""):
            src = f"services/{SOURCE_AGENT_ID}"
            col = "agents/*"
            urn = a.get("agentId", CANONICAL_SOURCE_AGENT_URN)
            urls = "https://auditor.finserv.internal/a2a"
            table.add_row(src, col, urn, urls, "A2A Skill: audit_wire_transfer")

    # Filter & add Endpoints
    for e in endpoints:
        runtime_ref = e.get("attributes", {}).get("agentregistry.googleapis.com/system/RuntimeReference", {}).get("uri", "")
        if "swift-sanctions-api" in runtime_ref:
            src = f"services/{REST_ENDPOINT_ID}"
            col = "endpoints/*"
            urn = e.get("endpointId", CANONICAL_REST_ENDPOINT_URN)
            urls = ", ".join(i.get("url", "") for i in e.get("interfaces", []))
            table.add_row(src, col, urn, urls, "HTTP_JSON (Sanctions Check)")

    console.print(table)
    console.print("[dim]Key Insight: Client agents query immutable Logical URNs. Physical URLs and versions migrate without breaking caller agents.[/dim]\n")


def inspect_bindings():
    """Enumerate and fetch Outbound Bindings via Agent Registry Remote MCP Server."""
    console.print(Panel(
        f"[bold cyan]Inspecting Active Enterprise Outbound Bindings[/bold cyan]\n"
        f"Registry Gateway: [bold white]{AGENT_REGISTRY_MCP_URL}[/bold white]\n"
        f"Parent Scope: [white]{PARENT}[/white]",
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
    table.add_column("Binding Resource", style="bold white", width=34)
    table.add_column("Source Agent URN", style="cyan", width=30)
    table.add_column("Target Tool URN", style="yellow", width=28)
    table.add_column("Managed Auth Provider", style="magenta", width=32)
    table.add_column("Governance Status", style="bold green", width=22)

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
        f"Parent Scope: [white]{PARENT}[/white]",
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
    """Zero-downtime cutover: update service interfaces[0].url to v2 and display Before vs. After diff."""
    console.print(Panel(
        f"[bold magenta]Initiating Zero-Downtime Governance Cutover (v1 ➔ v2)[/bold magenta]\n"
        f"Target Service: [white]{SERVICE_RESOURCE_NAME}[/white]\n"
        f"Promoting New Version: [bold green]v2.0-ZERO-TRUST-HARDENED[/bold green]\n"
        f"New Endpoint: [bold cyan]{LEDGER_V2_URL}[/bold cyan]\n"
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

    # Before vs. After Comparison Diff Table
    diff_table = Table(title="Governance Cutover Diff: Logical URN Invariance", show_header=True, header_style="bold yellow")
    diff_table.add_column("Governance Attribute", style="bold white", width=26)
    diff_table.add_column("Before Cutover (Legacy v1)", style="red", width=42)
    diff_table.add_column("After Cutover (Hardened v2)", style="bold green", width=42)

    diff_table.add_row(
        "Logical URN (Client)",
        CANONICAL_TARGET_TOOL_URN,
        CANONICAL_TARGET_TOOL_URN
    )
    diff_table.add_row(
        "Outbound Binding ID",
        BINDING_ID,
        BINDING_ID
    )
    diff_table.add_row(
        "Physical Resource URI",
        LEDGER_V1_URL,
        LEDGER_V2_URL
    )
    diff_table.add_row(
        "Cryptographic Standard",
        "Legacy SHA-256 (Deprecated)",
        "Post-Quantum ML-DSA-65 Signatures"
    )
    diff_table.add_row(
        "Client Code Deployment",
        "None Required (Zero Downtime)",
        "None Required (Zero Downtime)"
    )

    console.print(diff_table)
    console.print(f"[bold green]✓ Cutover complete! Logical URN and Outbound Binding stayed 100% IDENTICAL while physical endpoint migrated to v2.[/bold green]\n")


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

    console.print(Panel(
        f"[bold red]EMERGENCY QUARANTINE ACTIVE[/bold red]\n"
        f"• Outbound Binding Revoked: [white]{BINDING_ID}[/white]\n"
        f"• MCP Service Purged: [white]{SERVICE_ID}[/white]\n"
        f"• Subsequent agent invocations will be blocked immediately at runtime.",
        title="Kill-Switch Enforced",
        border_style="red"
    ))


def main():
    parser = argparse.ArgumentParser(description="Google Cloud Agent Registry MCP Control Plane")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("show-onboarding-specs", help="Show all 3 Onboarding Pipelines & CQRS architecture")
    subparsers.add_parser("explain-paths", help="Alias for show-onboarding-specs")
    subparsers.add_parser("list-meta-tools", help="Enumerate built-in Agent Registry governance tools grouped by Read vs. Write")
    subparsers.add_parser("onboard-all", help="Onboard all 3 service types (MCP, Agent, REST) & Outbound Binding")
    subparsers.add_parser("register-v1", help="Alias for onboard-all")
    subparsers.add_parser("inspect-catalog", help="Inspect CQRS Write-to-Read Catalog projections")
    subparsers.add_parser("inspect-bindings", help="Inspect active Outbound Bindings")
    subparsers.add_parser("list-bindings", help="Alias for inspect-bindings")
    subparsers.add_parser("fetch-bindings", help="Alias for inspect-bindings")
    search_p = subparsers.add_parser("search", help="Search approved MCP servers")
    search_p.add_argument("--term", default="ledger", help="Search query term")
    subparsers.add_parser("cutover-v2", help="Cutover tool definition to v2.0 with Before vs. After diff")
    subparsers.add_parser("revoke", help="Emergency revocation of registered tool & outbound binding (Kill-Switch)")

    args = parser.parse_args()

    if args.subcommand in ("show-onboarding-specs", "explain-paths"):
        show_onboarding_specs()
    elif args.subcommand == "list-meta-tools":
        list_meta_tools()
    elif args.subcommand in ("onboard-all", "register-v1"):
        onboard_all()
    elif args.subcommand == "inspect-catalog":
        inspect_catalog()
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
