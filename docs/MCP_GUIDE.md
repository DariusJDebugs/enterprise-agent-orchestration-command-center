# Model Context Protocol Guide

The system provides two MCP integration surfaces:

1. `POST /mcp` implements the tested JSON-RPC tool contract for initialize, ping, tools/list and tools/call.
2. `python -m app.mcp_server` starts the official FastMCP stdio adapter after the declared `mcp` dependency is installed.

Published tools include enterprise-knowledge search, vendor lookup, risk-signal checks and mission-summary retrieval. Tool execution still passes through the governance engine and records permission decisions.

Example JSON-RPC request:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

The HTTP contract is covered by automated tests. The stdio adapter is intentionally optional so the web application remains testable in offline environments where the SDK package is unavailable.
