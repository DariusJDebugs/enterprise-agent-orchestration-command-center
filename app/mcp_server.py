"""Official MCP Python SDK adapter.

Run after installing requirements:
    python -m app.mcp_server

The FastAPI application also exposes a JSON-RPC endpoint at POST /mcp so the
MVP can demonstrate and test its tool contract without a separate process.
"""
from __future__ import annotations

import json

from .config import Settings
from .services import build_services

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - SDK is an optional runtime in CI
    raise SystemExit("Install the official MCP Python SDK with: pip install mcp") from exc

services = build_services(Settings.from_env())
mcp = FastMCP("Enterprise Agent Orchestration Command Center")


@mcp.tool()
async def search_enterprise_knowledge(query: str, top_k: int = 6) -> str:
    """Search uploaded enterprise documents and return cited chunks."""
    result = await services.tools.call("search_enterprise_knowledge", {"query": query, "top_k": top_k})
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def lookup_vendor(vendor_name: str) -> str:
    """Look up vendor registration information through an approved connector."""
    result = await services.tools.call("lookup_vendor", {"vendor_name": vendor_name})
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def check_risk_signals(vendor_name: str) -> str:
    """Retrieve sanctions, adverse-media, continuity, and cyber signals."""
    result = await services.tools.call("check_risk_signals", {"vendor_name": vendor_name})
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def get_mission_summary(mission_id: str) -> str:
    """Return a persisted mission and task-state summary."""
    result = await services.tools.call("get_mission_summary", {"mission_id": mission_id})
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
