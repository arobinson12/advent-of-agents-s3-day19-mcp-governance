"""
FinServ Ledger MCP Server v1 (Legacy)
Streamable HTTP MCP Server exposing verify_ledger_transaction
"""
import os
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "finserv-ledger-mcp-v1",
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)

@mcp.tool(
    name="verify_ledger_transaction",
    description="Verify a financial ledger transaction ID and return compliance audit status."
)
def verify_ledger_transaction(transaction_id: str) -> dict:
    """Verify ledger transaction with Legacy v1 engine."""
    print(f"[FinServ Ledger v1] Verifying transaction: {transaction_id}")
    return {
        "status": "VERIFIED",
        "server_version": "v1.0-LEGACY",
        "transaction_id": transaction_id or "TX-9941",
        "amount": "$142,500.00",
        "audit_note": "Processed by Legacy Ledger MCP v1 (Deprecated)"
    }

app = mcp.streamable_http_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8081"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting FinServ Ledger MCP v1 on {host}:{port}/mcp ...")
    uvicorn.run(app, host=host, port=port)
