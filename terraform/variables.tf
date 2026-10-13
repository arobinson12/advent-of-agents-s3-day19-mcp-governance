variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
  default     = "bu2-prod-data"
}

variable "region" {
  description = "The Google Cloud Region for Agent Registry"
  type        = string
  default     = "us-central1"
}

variable "github_mcp_url" {
  description = "Physical URI for GitHub MCP Server (Cloud Run v1)"
  type        = string
  default     = "https://github-mcp-v1-918024802560.us-central1.run.app/mcp"
}

variable "agent_service_account" {
  description = "Agent Service Account / Principal to grant roles/agentidentity.user"
  type        = string
  default     = "918024802560-compute@developer.gserviceaccount.com"
}
