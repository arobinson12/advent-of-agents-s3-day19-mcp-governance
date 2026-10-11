output "ledger_mcp_urn" {
  description = "Canonical Logical URN for FinServ Ledger MCP"
  value       = "urn:mcp:${var.project_id}:${var.region}:finserv-ledger-mcp"
}

output "auditor_agent_urn" {
  description = "Canonical Logical URN for FinServ Auditor Agent"
  value       = "urn:agent:${var.project_id}:${var.region}:finserv-auditor-agent"
}

output "binding_id" {
  description = "Outbound Binding ID"
  value       = google_agent_registry_binding.auditor_to_ledger.binding_id
}
