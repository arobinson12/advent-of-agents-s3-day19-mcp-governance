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

variable "ledger_mcp_url" {
  description = "Physical URI for FinServ Ledger MCP Server"
  type        = string
  default     = "https://finserv-ledger-mcp-v1-918024802560.us-central1.run.app/mcp"
}
