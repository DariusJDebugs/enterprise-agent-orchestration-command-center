import pytest

from app.governance import GovernanceEngine


def test_explicit_tool_allowlists():
    governance = GovernanceEngine()
    allowed = governance.authorize_tool(tool_name="lookup_vendor", actor="vendor_intelligence", actor_role="agent")
    denied = governance.authorize_tool(tool_name="lookup_vendor", actor="knowledge", actor_role="agent")
    assert allowed.allowed is True
    assert denied.allowed is False


def test_high_risk_tool_requires_approval():
    governance = GovernanceEngine()
    pending = governance.authorize_tool(tool_name="submit_vendor_decision", actor="report", actor_role="agent", approved=False)
    approved = governance.authorize_tool(tool_name="submit_vendor_decision", actor="report", actor_role="agent", approved=True)
    assert pending.allowed is False and pending.requires_approval is True
    assert approved.allowed is True


def test_role_permission_hierarchy():
    governance = GovernanceEngine()
    governance.require("admin", "decide_approval")
    governance.require("risk_manager", "control_mission")
    with pytest.raises(PermissionError):
        governance.require("viewer", "create_mission")
