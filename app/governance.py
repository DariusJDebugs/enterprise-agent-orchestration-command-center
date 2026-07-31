from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "analyst": {"read", "create_mission", "upload_document", "run_safe_tool"},
    "risk_manager": {"read", "create_mission", "upload_document", "run_safe_tool", "control_mission", "decide_approval", "run_sensitive_tool"},
    "admin": {"*"},
    "agent": {"run_agent_tool"},
}

ROLE_RANK = {"viewer": 0, "analyst": 1, "risk_manager": 2, "admin": 3, "agent": 1}


class AuthorizationError(PermissionError):
    pass


@dataclass(slots=True)
class ToolPolicy:
    risk_level: str
    allowed_agents: set[str]
    allowed_roles: set[str]
    requires_approval: bool = False


@dataclass(slots=True)
class PermissionDecision:
    allowed: bool
    reason: str
    risk_level: str
    requires_approval: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
        }


class GovernanceEngine:
    TOOL_POLICIES: dict[str, ToolPolicy] = {
        "search_enterprise_knowledge": ToolPolicy("low", {"knowledge", "security", "compliance", "financial", "operations", "reviewer", "red_team", "report"}, {"analyst", "risk_manager", "admin"}),
        "lookup_vendor": ToolPolicy("medium", {"vendor_intelligence"}, {"risk_manager", "admin"}),
        "check_risk_signals": ToolPolicy("medium", {"vendor_intelligence", "reviewer", "red_team"}, {"risk_manager", "admin"}),
        "get_mission_summary": ToolPolicy("low", {"coordinator", "reviewer", "red_team", "report"}, {"analyst", "risk_manager", "admin", "viewer"}),
        "submit_vendor_decision": ToolPolicy("high", {"report"}, {"risk_manager", "admin"}, requires_approval=True),
    }

    def has_permission(self, role: str, permission: str) -> bool:
        permissions = ROLE_PERMISSIONS.get(role, set())
        return "*" in permissions or permission in permissions

    def require(self, role: str, permission: str) -> None:
        if not self.has_permission(role, permission):
            raise AuthorizationError(f"Role '{role}' lacks permission '{permission}'")

    def authorize_tool(self, *, tool_name: str, actor: str, actor_role: str, approved: bool = False) -> PermissionDecision:
        policy = self.TOOL_POLICIES.get(tool_name)
        if not policy:
            return PermissionDecision(False, "No explicit allow policy exists for this tool", "high")
        if actor_role == "agent":
            if actor not in policy.allowed_agents:
                return PermissionDecision(False, f"Agent '{actor}' is outside the tool allowlist", policy.risk_level, policy.requires_approval)
        elif actor_role not in policy.allowed_roles:
            return PermissionDecision(False, f"Role '{actor_role}' is outside the tool allowlist", policy.risk_level, policy.requires_approval)
        if policy.requires_approval and not approved:
            return PermissionDecision(False, "High-risk tool requires an approved human decision", policy.risk_level, True)
        return PermissionDecision(True, "Explicit policy allow", policy.risk_level, policy.requires_approval)

    def public_matrix(self) -> dict[str, Any]:
        return {
            "roles": {role: sorted(permissions) for role, permissions in ROLE_PERMISSIONS.items()},
            "tool_policies": {
                name: {
                    "risk_level": policy.risk_level,
                    "allowed_agents": sorted(policy.allowed_agents),
                    "allowed_roles": sorted(policy.allowed_roles),
                    "requires_approval": policy.requires_approval,
                }
                for name, policy in self.TOOL_POLICIES.items()
            },
        }
