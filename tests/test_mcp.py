def test_mcp_initialize_and_tools_list(client):
    initialized = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26"},
    }).json()
    assert initialized["result"]["serverInfo"]["name"] == "enterprise-command-center"

    tools = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}).json()
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert {"search_enterprise_knowledge", "lookup_vendor", "check_risk_signals"} <= names


def test_mcp_tool_call(client):
    called = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "lookup_vendor", "arguments": {"vendor_name": "Northstar Cloud Systems"}},
    }).json()
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"]["vendor_name"] == "Northstar Cloud Systems"
