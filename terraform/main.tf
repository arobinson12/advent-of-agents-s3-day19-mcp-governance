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
# PIPELINE 3: Declarative GitOps IaC for GitHub MCP + Managed Auth Governance
# Demonstrating the 3-Part Handshake: Service + AuthProvider/IAM + Outbound Binding
# ==============================================================================

# ------------------------------------------------------------------------------
# PART 1: Register Services (agentregistry.googleapis.com) - Zero Secrets Held!
# ------------------------------------------------------------------------------

# 1. 3P MCP Server: GitHub Security & Audit MCP Server
resource "google_agent_registry_service" "github_mcp" {
  project      = var.project_id
  location     = var.region
  service_id   = "github-mcp"
  display_name = "GitHub Enterprise Security & Audit MCP Server"
  description  = "Admin-approved 3P GitHub MCP Server with bound AuthProvider for inspecting repositories and commit audits"

  mcp_server_spec {
    type    = "TOOL_SPEC"
    content = file("${path.module}/../specs/github-toolspec.json")
  }

  interface {
    url      = var.github_mcp_url
    protocol = "STREAMABLE_HTTP"
  }
}

# 2. Autonomous Agent: SecOps Compliance & Release Auditor (A2A v1.0 Agent Card)
resource "google_agent_registry_service" "secops_auditor" {
  project      = var.project_id
  location     = var.region
  service_id   = "secops-auditor"
  display_name = "SecOps Compliance & Release Auditor Agent"
  description  = "Autonomous repository security and release auditor agent powered by Google ADK"

  agent_spec {
    type    = "A2A_AGENT_CARD"
    content = file("${path.module}/../specs/agent-card.json")
  }

  interface {
    url      = "https://secops-auditor.internal/a2a"
    protocol = "JSONRPC"
  }
}

# 3. Direct REST Endpoint: CVE Advisory Vulnerability Feed (No Spec / Direct Interface)
resource "google_agent_registry_service" "cve_advisory_api" {
  project      = var.project_id
  location     = var.region
  service_id   = "cve-advisory-api"
  display_name = "NIST / MITRE CVE Advisory Screening API"
  description  = "Real-time vulnerability database screening API for known CVE identifiers"

  endpoint_spec {
    type = "NO_SPEC"
  }

  interface {
    url      = "https://api.cve.mitre.org/v1"
    protocol = "HTTP_JSON"
  }
}

# ------------------------------------------------------------------------------
# PART 2: Managed AuthProvider & IAM Permissions (agentidentity.googleapis.com)
# CRITICAL: Grant roles/agentidentity.user to Agent Principal so RetrieveCredentials succeeds!
# ------------------------------------------------------------------------------

# GitHub Authentication Provider (supports Fine-Grained PAT apiKey & OAuth 3LO)
# Real credentials live in Secret Manager; the AuthProvider brokers retrieval dynamically.
resource "google_agent_identity_auth_provider" "github_auth" {
  project          = var.project_id
  location         = var.region
  auth_provider_id = "github-auth"
  description      = "Managed GitHub Auth Provider for GitHub MCP Server (Fine-Grained PAT apiKey / 3LO OAuth)"

  api_key {}

  # For 3-Legged OAuth (3LO) Web Flow, configure:
  # three_legged_oauth {
  #   client_id         = var.github_oauth_client_id
  #   authorization_url = "https://github.com/login/oauth/authorize"
  #   token_url         = "https://github.com/login/oauth/access_token"
  #   # Deterministic redirectUrl provided by Google Cloud:
  #   # https://iamconnectorcredentials.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/connectors/github-auth/oauthcallback
  # }
}

# #1 GOTCHA: Grant roles/agentidentity.user on the AuthProvider to the Agent Service Account
resource "google_agent_identity_auth_provider_iam_member" "agent_auth_user" {
  project          = var.project_id
  location         = var.region
  auth_provider_id = google_agent_identity_auth_provider.github_auth.auth_provider_id
  role             = "roles/agentidentity.user"
  member           = "serviceAccount:${var.agent_service_account}"
}

# Optional connector caller role if using external IAM connectors
resource "google_project_iam_member" "agent_connector_user" {
  project = var.project_id
  role    = "roles/iamconnectors.user"
  member  = "serviceAccount:${var.agent_service_account}"
}

# ------------------------------------------------------------------------------
# PART 3: Wire the Outbound Binding with AuthProvider Enforcement
# Connects source Agent -> target MCP Server and attaches Managed AuthProvider
# ------------------------------------------------------------------------------

resource "google_agent_registry_binding" "auditor_to_github" {
  project    = var.project_id
  location   = var.region
  binding_id = "auditor-to-github-binding"

  display_name = "SecOps Auditor to GitHub MCP Binding"
  description  = "Admin-approved Outbound Binding linking SecOps Auditor to GitHub MCP with bound AuthProvider (github-auth)"

  source {
    identifier = "urn:agent:${var.project_id}:${var.region}:secops-auditor"
  }

  target {
    identifier = "urn:mcp:${var.project_id}:${var.region}:github-mcp"
  }

  auth_provider_binding {
    auth_provider = google_agent_identity_auth_provider.github_auth.id
    scopes        = ["repo", "read:org"]
  }

  depends_on = [
    google_agent_registry_service.github_mcp,
    google_agent_registry_service.secops_auditor,
    google_agent_identity_auth_provider_iam_member.agent_auth_user
  ]
}

# ==============================================================================
# BONUS EXAMPLE: Pattern Invariance for Figma MCP + OAuth 3LO
# The exact same 3-part handshake governs design and SaaS tools!
# ==============================================================================
#
# resource "google_agent_registry_service" "figma_mcp" {
#   project      = var.project_id
#   location     = var.region
#   service_id   = "figma-mcp"
#   display_name = "Figma Design System MCP Server"
#   description  = "Enterprise design tokens and component audit tool server"
#   interface {
#     url      = "https://figma-mcp.internal/mcp"
#     protocol = "STREAMABLE_HTTP"
#   }
# }
#
# resource "google_agent_identity_auth_provider" "figma_auth" {
#   project          = var.project_id
#   location         = var.region
#   auth_provider_id = "figma-oauth"
#   description      = "Figma OAuth 3LO AuthProvider"
#   three_legged_oauth {
#     client_id         = var.figma_client_id
#     authorization_url = "https://www.figma.com/oauth"
#     token_url         = "https://api.figma.com/v1/oauth/token"
#   }
# }
#
# resource "google_agent_registry_binding" "designer_to_figma" {
#   project    = var.project_id
#   location   = var.region
#   binding_id = "designer-to-figma-binding"
#   source {
#     identifier = "urn:agent:${var.project_id}:${var.region}:ui-designer-agent"
#   }
#   target {
#     identifier = "urn:mcp:${var.project_id}:${var.region}:figma-mcp"
#   }
#   auth_provider_binding {
#     auth_provider = google_agent_identity_auth_provider.figma_auth.id
#     scopes        = ["file_read"]
#   }
# }
