from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .connectors import ConnectorRegistry
from .governance import AuthorizationError, GovernanceEngine
from .rag import RAGService
from .repository import Repository


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def public_dict(self, governance: GovernanceEngine) -> dict[str, Any]:
        policy = governance.TOOL_POLICIES.get(self.name)
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "policy": {
                "risk_level": policy.risk_level if policy else "high",
                "requires_approval": policy.requires_approval if policy else True,
                "allowed_agents": sorted(policy.allowed_agents) if policy else [],
                "allowed_roles": sorted(policy.allowed_roles) if policy else [],
            },
        }


class ToolRegistry:
    def __init__(self, rag: RAGService, connectors: ConnectorRegistry, repository: Repository, governance: GovernanceEngine):
        self.rag = rag
        self.connectors = connectors
        self.repository = repository
        self.governance = governance
        self._tools: dict[str, ToolDefinition] = {}
        self._register_defaults()

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def list(self) -> list[dict[str, Any]]:
        return [tool.public_dict(self.governance) for tool in self._tools.values()]

    async def call(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        actor: str = "system",
        actor_role: str = "admin",
        mission_id: str | None = None,
        task_id: str | None = None,
        approved: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Unknown tool: {name}")
        decision = self.governance.authorize_tool(
            tool_name=name, actor=actor, actor_role=actor_role, approved=approved,
        )
        if not decision.allowed:
            if mission_id:
                self.repository.add_tool_call(
                    mission_id, task_id, name, arguments,
                    {"error": "AuthorizationError", "message": decision.reason}, "denied",
                    actor=actor, actor_role=actor_role, permission_decision="denied",
                    risk_level=decision.risk_level, idempotency_key=idempotency_key,
                )
                self.repository.add_security_incident(
                    mission_id=mission_id, incident_type="unauthorized_tool_access",
                    severity="high", status="blocked",
                    details={"tool": name, "actor": actor, "role": actor_role, "reason": decision.reason},
                )
            raise AuthorizationError(decision.reason)

        cache_key = f"tool:{mission_id or 'global'}:{name}:{idempotency_key}" if idempotency_key else None
        if cache_key:
            cached = self.repository.get_idempotent_result(cache_key)
            if cached is not None:
                if mission_id:
                    self.repository.add_tool_call(
                        mission_id, task_id, name, arguments, cached, "replayed",
                        actor=actor, actor_role=actor_role, permission_decision="allowed",
                        risk_level=decision.risk_level, idempotency_key=idempotency_key,
                    )
                return {**cached, "idempotent_replay": True}

        start = time.perf_counter()
        try:
            result = await tool.handler(dict(arguments))
            latency_ms = (time.perf_counter() - start) * 1000
            if cache_key:
                self.repository.save_idempotent_result(cache_key, "tool_call", result)
            if mission_id:
                self.repository.add_tool_call(
                    mission_id, task_id, name, arguments, result, "completed",
                    actor=actor, actor_role=actor_role, permission_decision="allowed",
                    risk_level=decision.risk_level, latency_ms=latency_ms,
                    idempotency_key=idempotency_key,
                )
            return result
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            if mission_id:
                self.repository.add_tool_call(
                    mission_id, task_id, name, arguments,
                    {"error": type(exc).__name__, "message": str(exc)}, "failed",
                    actor=actor, actor_role=actor_role, permission_decision="allowed",
                    risk_level=decision.risk_level, latency_ms=latency_ms,
                    idempotency_key=idempotency_key,
                )
            raise

    def _register_defaults(self) -> None:
        async def search_knowledge(arguments: dict[str, Any]) -> dict[str, Any]:
            query = str(arguments.get("query", "")).strip()
            top_k = int(arguments.get("top_k", 6))
            if not query:
                raise ValueError("query is required")
            matches = self.rag.search(query, top_k=max(1, min(top_k, 20)), include_quarantined=False)
            return {"query": query, "matches": [match.as_dict() for match in matches], "quarantine_enforced": True}

        async def lookup_vendor(arguments: dict[str, Any]) -> dict[str, Any]:
            return await self.connectors.execute("vendor_registry", "lookup_vendor", arguments)

        async def check_risk_signals(arguments: dict[str, Any]) -> dict[str, Any]:
            return await self.connectors.execute("risk_signals", "check_risk_signals", arguments)

        async def get_mission_summary(arguments: dict[str, Any]) -> dict[str, Any]:
            mission_id = str(arguments.get("mission_id", ""))
            mission = self.repository.get_mission(mission_id)
            if not mission:
                raise ValueError("mission not found")
            tasks = self.repository.list_tasks(mission_id)
            return {"mission": mission, "task_statuses": {task["agent_name"]: task["status"] for task in tasks}}

        async def submit_vendor_decision(arguments: dict[str, Any]) -> dict[str, Any]:
            return {
                "submitted": True,
                "vendor_name": arguments.get("vendor_name"),
                "decision": arguments.get("decision"),
                "destination": "demo_procurement_system",
            }

        definitions = [
            ToolDefinition("search_enterprise_knowledge", "Search uploaded enterprise documents and return source-cited, non-quarantined chunks.", {"type":"object","properties":{"query":{"type":"string"},"top_k":{"type":"integer","minimum":1,"maximum":20}},"required":["query"]}, search_knowledge),
            ToolDefinition("lookup_vendor", "Look up vendor-master and corporate-registration information.", {"type":"object","properties":{"vendor_name":{"type":"string"}},"required":["vendor_name"]}, lookup_vendor),
            ToolDefinition("check_risk_signals", "Retrieve sanctions, adverse-media, continuity, and cyber-risk signals.", {"type":"object","properties":{"vendor_name":{"type":"string"}},"required":["vendor_name"]}, check_risk_signals),
            ToolDefinition("get_mission_summary", "Return a persisted mission and its current task statuses.", {"type":"object","properties":{"mission_id":{"type":"string"}},"required":["mission_id"]}, get_mission_summary),
            ToolDefinition("submit_vendor_decision", "Submit an approved vendor decision to the procurement system.", {"type":"object","properties":{"vendor_name":{"type":"string"},"decision":{"type":"string"}},"required":["vendor_name","decision"]}, submit_vendor_decision),
        ]
        for definition in definitions:
            self.register(definition)
