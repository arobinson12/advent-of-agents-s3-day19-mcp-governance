terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.10.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ==============================================================================
# PIPELINE 3: Declarative GitOps IaC via Google Cloud Agent Registry
# ==============================================================================

# 1. Onboarding an MCP Tool Server (Declarative ToolSpec)
resource "google_agent_registry_service" "ledger_mcp" {
  project      = var.project_id
  location     = var.region
  service_id   = "finserv-ledger-mcp"
  display_name = "FinServ Production Ledger MCP"
  description  = "Enterprise SecOps-approved MCP server for verifying financial transactions"

  mcp_server_spec {
    type    = "TOOL_SPEC"
    content = file("${path.module}/../specs/toolspec.json")
  }

  interface {
    url      = var.ledger_mcp_url
    protocol = "STREAMABLE_HTTP"
  }
}

# 2. Onboarding an Autonomous Agent (A2A v1.0 Agent Card)
resource "google_agent_registry_service" "auditor_agent" {
  project      = var.project_id
  location     = var.region
  service_id   = "finserv-auditor-agent"
  display_name = "FinServ Compliance & Security Auditor Agent"
  description  = "Autonomous financial services auditing and compliance agent"

  agent_spec {
    type    = "A2A_AGENT_CARD"
    content = file("${path.module}/../specs/agent-card.json")
  }

  interface {
    url      = "https://auditor.finserv.internal/a2a"
    protocol = "JSONRPC"
  }
}

# 3. Onboarding a Legacy REST API Endpoint (No Spec / Direct Interface)
resource "google_agent_registry_service" "swift_api" {
  project      = var.project_id
  location     = var.region
  service_id   = "swift-sanctions-api"
  display_name = "SWIFT OFAC Sanctions Screening API"
  description  = "Real-time sanctions and PEP compliance check API endpoint"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interface {
    url      = "https://api.swift-screening.internal/v1/check"
    protocol = "HTTP_JSON"
  }
}

# 4. Creating an Outbound Binding with Managed Auth Connector
resource "google_agent_registry_binding" "auditor_to_ledger" {
  project    = var.project_id
  location   = var.region
  binding_id = "auditor-to-ledger-binding"

  source {
    identifier = "urn:agent:${var.project_id}:${var.region}:finserv-auditor-agent"
  }

  target {
    identifier = "urn:mcp:${var.project_id}:${var.region}:finserv-ledger-mcp"
  }

  auth_provider_binding {
    auth_provider = "projects/${var.project_id}/locations/${var.region}/connectors/ledger-oauth"
  }

  depends_on = [
    google_agent_registry_service.ledger_mcp,
    google_agent_registry_service.auditor_agent
  ]
}
