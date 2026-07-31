from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Any

from .agents.base import AgentContext, BaseAgent
from .agents.core import AGENT_TYPES
from .evaluation import EvaluationService
from .llm import LLMProvider
from .repository import Repository, utc_now
from .tools import ToolRegistry


class BudgetExceeded(RuntimeError):
    pass


class MissionStopped(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GraphNode:
    name: str
    title: str
    dependencies: tuple[str, ...] = ()


class MissionGraph:
    def __init__(self, nodes: list[GraphNode]):
        self.nodes = {node.name: node for node in nodes}
        self._validate()

    def _validate(self) -> None:
        for node in self.nodes.values():
            missing = set(node.dependencies) - self.nodes.keys()
            if missing:
                raise ValueError(f"Node {node.name} has missing dependencies: {sorted(missing)}")
        visited: set[str] = set()
        active: set[str] = set()

        def visit(name: str) -> None:
            if name in active:
                raise ValueError("Mission graph contains a cycle")
            if name in visited:
                return
            active.add(name)
            for dependency in self.nodes[name].dependencies:
                visit(dependency)
            active.remove(name)
            visited.add(name)

        for name in self.nodes:
            visit(name)

    def layers(self) -> list[list[GraphNode]]:
        completed: set[str] = set()
        pending = set(self.nodes)
        layers: list[list[GraphNode]] = []
        while pending:
            ready = [
                self.nodes[name] for name in self.nodes
                if name in pending and set(self.nodes[name].dependencies) <= completed
            ]
            if not ready:
                raise RuntimeError("Graph cannot make progress")
            layers.append(ready)
            completed.update(node.name for node in ready)
            pending -= {node.name for node in ready}
        return layers


DEFAULT_GRAPH = MissionGraph([
    GraphNode("coordinator", "Plan governed mission"),
    GraphNode("knowledge", "Retrieve security-cleared enterprise knowledge", ("coordinator",)),
    GraphNode("vendor_intelligence", "Query permission-scoped vendor and risk connectors", ("coordinator",)),
    GraphNode("security", "Verify untrusted-document isolation", ("knowledge",)),
    GraphNode("compliance", "Map compliance and privacy controls", ("knowledge", "vendor_intelligence", "security")),
    GraphNode("financial", "Assess financial and continuity risk", ("knowledge", "vendor_intelligence")),
    GraphNode("operations", "Assess operational resilience", ("knowledge", "vendor_intelligence", "security")),
    GraphNode("reviewer", "Challenge evidence and determine risk posture", ("compliance", "financial", "operations", "security", "vendor_intelligence")),
    GraphNode("draft_report", "Create traceable decision draft", ("reviewer", "compliance", "financial", "operations", "security", "vendor_intelligence")),
    GraphNode("red_team", "Adversarially validate and reject weak drafts", ("draft_report", "reviewer")),
    GraphNode("report", "Repair and publish final evidence report", ("red_team", "draft_report", "reviewer", "compliance", "financial", "operations", "security", "vendor_intelligence")),
])


class Orchestrator:
    def __init__(
        self,
        repository: Repository,
        tools: ToolRegistry,
        llm: LLMProvider,
        evaluation: EvaluationService,
        *,
        graph: MissionGraph = DEFAULT_GRAPH,
        step_delay_ms: int = 100,
        max_retries: int = 2,
        approval_risk_levels: set[str] | None = None,
    ):
        self.repository = repository
        self.tools = tools
        self.llm = llm
        self.evaluation = evaluation
        self.graph = graph
        self.step_delay_ms = max(0, step_delay_ms)
        self.max_retries = max(0, max_retries)
        self.approval_risk_levels = approval_risk_levels or {"high", "critical"}
        self.agents: dict[str, BaseAgent] = {name: agent_type() for name, agent_type in AGENT_TYPES.items()}
        missing = set(self.graph.nodes) - self.agents.keys()
        if missing:
            raise ValueError(f"No agent implementations for graph nodes: {sorted(missing)}")

    def create_mission(
        self,
        title: str,
        vendor_name: str,
        objective: str,
        *,
        owner_role: str = "analyst",
        budget_usd: float = 2.0,
        token_budget: int = 50_000,
        require_approval_for_high_risk: bool = True,
        proof_scenario: str = "standard",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if idempotency_key:
            existing = self.repository.get_mission_by_idempotency_key(idempotency_key)
            if existing:
                return existing
        mission_id = str(uuid.uuid4())
        if proof_scenario == "budget_limit":
            budget_usd = min(budget_usd, 0.00001)
            token_budget = min(token_budget, 120)
        mission = {
            "id": mission_id,
            "title": title,
            "vendor_name": vendor_name,
            "objective": objective,
            "status": "queued",
            "risk_level": "unknown",
            "owner_role": owner_role,
            "control_state": "active",
            "budget_usd": budget_usd,
            "token_budget": token_budget,
            "approval_policy": "high_and_critical" if require_approval_for_high_risk else "none",
            "proof_scenario": proof_scenario,
            "idempotency_key": idempotency_key,
            "context": {
                "graph": [
                    {"name": node.name, "title": node.title, "dependencies": list(node.dependencies)}
                    for node in self.graph.nodes.values()
                ],
                "agent_outputs": {},
                "proof_scenario": proof_scenario,
                "recovery": {},
            },
        }
        self.repository.create_mission(mission)
        tasks = [
            {
                "id": f"{mission_id}:{node.name}",
                "agent_name": node.name,
                "title": node.title,
                "status": "pending",
                "dependencies": [f"{mission_id}:{dependency}" for dependency in node.dependencies],
                "input": {"mission_objective": objective, "proof_scenario": proof_scenario},
                "max_attempts": self.max_retries + 1,
                "idempotency_key": f"task:{mission_id}:{node.name}",
            }
            for node in self.graph.nodes.values()
        ]
        self.repository.create_tasks(mission_id, tasks)
        self.repository.add_event(
            mission_id, "mission.created", owner_role,
            "Mission created with governance, budget, approval, and audit policies.",
            {"task_count": len(tasks), "budget_usd": budget_usd, "token_budget": token_budget, "proof_scenario": proof_scenario},
        )
        return self.repository.get_mission(mission_id) or mission

    async def run_mission(self, mission_id: str) -> dict[str, Any]:
        mission = self.repository.get_mission(mission_id)
        if not mission:
            raise ValueError("Mission not found")
        if mission["status"] in {"completed", "stopped", "budget_exceeded"}:
            return mission
        if mission["status"] == "awaiting_approval" and not self._approval_granted(mission_id):
            return mission

        self.repository.update_mission(mission_id, status="running", control_state="active")
        self.repository.add_event(mission_id, "mission.started", "orchestrator", "Governed mission execution started or resumed.")
        shared_state = dict(mission.get("context", {}))
        shared_state.setdefault("agent_outputs", {})

        try:
            for layer_index, layer in enumerate(self.graph.layers(), start=1):
                await self._wait_for_operator_control(mission_id)
                if any(node.name == "draft_report" for node in layer):
                    gate_result = self._enforce_human_approval_gate(mission_id, shared_state)
                    if gate_result == "waiting":
                        return self.repository.get_mission(mission_id) or mission
                    if gate_result == "rejected":
                        return self.repository.get_mission(mission_id) or mission

                self.repository.add_event(
                    mission_id, "graph.layer_started", "orchestrator",
                    f"Executing graph layer {layer_index} with {len(layer)} ready agent(s).",
                    {"agents": [node.name for node in layer]},
                )
                results = await asyncio.gather(*[
                    self._execute_node(mission_id, node, shared_state) for node in layer
                ], return_exceptions=True)
                for node, result in zip(layer, results, strict=True):
                    if isinstance(result, Exception):
                        raise result
                    shared_state["agent_outputs"][node.name] = result
                self.repository.update_mission(mission_id, context_json=shared_state)
                self.repository.add_checkpoint(mission_id, None, {
                    "layer": layer_index,
                    "completed_agents": list(shared_state["agent_outputs"]),
                    "shared_state": shared_state,
                })

            report_output = shared_state["agent_outputs"]["report"]
            reviewer_output = shared_state["agent_outputs"]["reviewer"]
            report_markdown = report_output.get("data", {}).get("report_markdown", "")
            risk_level = reviewer_output.get("data", {}).get("risk_level", "unknown")
            self.repository.update_mission(
                mission_id, status="completed", risk_level=risk_level,
                final_report=report_markdown, context_json=shared_state,
            )
            self.repository.add_event(
                mission_id, "mission.completed", "orchestrator",
                f"Mission completed with {risk_level} risk after governance and red-team gates.",
                {
                    "risk_level": risk_level,
                    "audit_chain": self.repository.verify_audit_chain(mission_id),
                    "quality": report_output.get("data", {}).get("quality", {}),
                },
            )
        except BudgetExceeded as exc:
            self.repository.update_mission(mission_id, status="budget_exceeded", control_state="stopped", context_json=shared_state)
            self._stop_pending_tasks(mission_id, "Budget limit enforced")
            self.repository.add_event(mission_id, "budget.exceeded", "budget_governor", str(exc), {})
        except MissionStopped as exc:
            self.repository.update_mission(mission_id, status="stopped", control_state="stopped", context_json=shared_state)
            self._stop_pending_tasks(mission_id, str(exc))
            self.repository.add_event(mission_id, "mission.stopped", "operator", str(exc), {})
        except Exception as exc:
            self.repository.update_mission(mission_id, status="failed", context_json=shared_state)
            self.repository.add_event(
                mission_id, "mission.failed", "orchestrator", f"Mission failed: {exc}",
                {"exception": type(exc).__name__, "traceback": traceback.format_exc(limit=10)},
            )
        return self.repository.get_mission(mission_id) or mission

    async def _wait_for_operator_control(self, mission_id: str) -> None:
        while True:
            mission = self.repository.get_mission(mission_id)
            if not mission:
                raise MissionStopped("Mission disappeared during execution")
            state = mission.get("control_state", "active")
            if state == "stopped":
                raise MissionStopped("Execution stopped by an authorized operator")
            if state != "paused":
                if mission["status"] == "paused":
                    self.repository.update_mission(mission_id, status="running")
                return
            self.repository.update_mission(mission_id, status="paused")
            await asyncio.sleep(0.05)

    def _approval_granted(self, mission_id: str) -> bool:
        approvals = self.repository.list_approvals(mission_id)
        return bool(approvals and approvals[-1]["status"] == "approved")

    def _enforce_human_approval_gate(self, mission_id: str, shared_state: dict[str, Any]) -> str:
        mission = self.repository.get_mission(mission_id) or {}
        reviewer = shared_state.get("agent_outputs", {}).get("reviewer", {})
        risk_level = reviewer.get("data", {}).get("risk_level", "unknown")
        self.repository.update_mission(mission_id, risk_level=risk_level)
        if mission.get("approval_policy") == "none" or risk_level not in self.approval_risk_levels:
            return "not_required"
        approvals = self.repository.list_approvals(mission_id)
        if approvals:
            latest = approvals[-1]
            if latest["status"] == "approved":
                self.repository.add_event(mission_id, "approval.consumed", latest.get("decided_by") or "risk_manager", "Approved high-risk decision released to downstream reporting.", {"approval_id": latest["id"]})
                return "approved"
            if latest["status"] == "rejected":
                self.repository.update_mission(mission_id, status="stopped", control_state="stopped")
                self._stop_pending_tasks(mission_id, "Human approval rejected")
                self.repository.add_event(mission_id, "approval.rejected", latest.get("decided_by") or "risk_manager", "Human reviewer rejected the high-risk decision.", {"approval_id": latest["id"]})
                return "rejected"
            self.repository.update_mission(mission_id, status="awaiting_approval", control_state="paused")
            return "waiting"
        approval_id = self.repository.create_approval(
            mission_id, "publish_high_risk_vendor_decision", "reviewer", risk_level,
            f"The reviewer classified this mission as {risk_level}; publication requires risk-manager approval.",
            {"reviewer_output": reviewer.get("data", {}), "vendor_name": mission.get("vendor_name")},
        )
        self.repository.update_mission(mission_id, status="awaiting_approval", control_state="paused")
        self.repository.add_event(
            mission_id, "approval.requested", "governance_gate",
            f"Execution paused for human approval of a {risk_level}-risk decision.",
            {"approval_id": approval_id, "risk_level": risk_level},
        )
        self.repository.add_checkpoint(mission_id, None, {"state": "awaiting_approval", "shared_state": shared_state})
        return "waiting"

    async def _execute_node(self, mission_id: str, node: GraphNode, shared_state: dict[str, Any]) -> dict[str, Any]:
        task_id = f"{mission_id}:{node.name}"
        task = self.repository.get_task(task_id)
        mission = self.repository.get_mission(mission_id)
        if not task or not mission:
            raise RuntimeError(f"Missing persisted state for node {node.name}")
        if task["status"] == "completed":
            return task["output"]
        await self._wait_for_operator_control(mission_id)
        self._assert_budget_available(mission)

        max_attempts = int(task.get("max_attempts", self.max_retries + 1))
        last_error: Exception | None = None
        for attempt in range(int(task.get("attempts", 0)) + 1, max_attempts + 1):
            span_id = str(uuid.uuid4())
            start = time.perf_counter()
            self.repository.update_task(task_id, status="running", started_at=utc_now(), error=None, attempts=attempt)
            self.repository.add_event(
                mission_id, "agent.started" if attempt == 1 else "agent.retry_started", node.name,
                f"{self.agents[node.name].display_name} attempt {attempt}/{max_attempts}: {node.title}.",
                {"task_id": task_id, "dependencies": list(node.dependencies), "attempt": attempt, "span_id": span_id},
            )
            if self.step_delay_ms:
                await asyncio.sleep(self.step_delay_ms / 1000)
            upstream = {
                dependency: shared_state.get("agent_outputs", {}).get(dependency, {})
                for dependency in node.dependencies
            }
            trace_input = {
                "system_prompt": self.agents[node.name].system_prompt,
                "mission": {"id": mission_id, "vendor_name": mission["vendor_name"], "objective": mission["objective"]},
                "upstream_agents": list(upstream),
                "attempt": attempt,
            }
            context = AgentContext(
                mission=self.repository.get_mission(mission_id) or mission,
                task=self.repository.get_task(task_id) or task,
                upstream=upstream,
                shared_state=shared_state,
                tools=self.tools,
                repository=self.repository,
                llm=self.llm,
                evaluation=self.evaluation,
                attempt=attempt,
            )
            try:
                result = await self.agents[node.name].execute(context)
                output = result.as_dict()
                latency_ms = (time.perf_counter() - start) * 1000
                token_usage = self._estimate_tokens(trace_input) + self._estimate_tokens(output)
                cost_usd = token_usage * 0.000002
                usage = self.repository.increment_usage(mission_id, token_usage, cost_usd)
                if usage.get("tokens_used", 0) > usage.get("token_budget", 0) or usage.get("spent_usd", 0) > usage.get("budget_usd", 0):
                    raise BudgetExceeded(
                        f"Mission budget stopped execution at {usage.get('tokens_used')} tokens / ${usage.get('spent_usd', 0):.6f}."
                    )
                trace = {"span_id": span_id, "attempt": attempt, "input": trace_input, "output_summary": output.get("summary")}
                self.repository.update_task(
                    task_id, status="completed", output_json=output, completed_at=utc_now(),
                    token_usage=token_usage, cost_usd=cost_usd, latency_ms=latency_ms, trace_json=trace,
                )
                self.repository.add_trace(
                    mission_id, task_id, span_id, "agent_execution", node.name,
                    trace_input, output, "completed", latency_ms=latency_ms, token_usage=token_usage, cost_usd=cost_usd,
                )
                self.repository.add_metric(mission_id, task_id, "latency", latency_ms, "ms", {"agent": node.name})
                self.repository.add_metric(mission_id, task_id, "tokens", token_usage, "tokens", {"agent": node.name})
                self.repository.add_metric(mission_id, task_id, "cost", cost_usd, "usd", {"agent": node.name})
                if node.name == "report":
                    quality = output.get("data", {}).get("quality", {})
                    self.repository.add_metric(mission_id, task_id, "groundedness", quality.get("groundedness", {}).get("score", 0), "score", {"agent": node.name})
                self.repository.add_event(
                    mission_id, "agent.completed", node.name, result.summary,
                    {"task_id": task_id, "attempt": attempt, "confidence": output["confidence"], "latency_ms": round(latency_ms, 2), "tokens": token_usage, "cost_usd": cost_usd},
                )
                for message in result.messages:
                    self.repository.add_message(
                        mission_id, node.name, str(message.get("recipient", "orchestrator")),
                        str(message.get("content", "")), {"type": message.get("type", "message"), "span_id": span_id},
                    )
                return output
            except BudgetExceeded:
                raise
            except Exception as exc:
                last_error = exc
                latency_ms = (time.perf_counter() - start) * 1000
                self.repository.add_trace(
                    mission_id, task_id, span_id, "agent_execution", node.name,
                    trace_input, {"error": type(exc).__name__, "message": str(exc)}, "failed", latency_ms=latency_ms,
                )
                if attempt < max_attempts:
                    self.repository.update_task(task_id, status="retrying", error=str(exc), latency_ms=latency_ms)
                    self.repository.add_event(
                        mission_id, "agent.retry_scheduled", node.name,
                        f"Transient failure captured; retry {attempt + 1}/{max_attempts} scheduled.",
                        {"task_id": task_id, "attempt": attempt, "error": str(exc)},
                    )
                    shared_state.setdefault("recovery", {})[node.name] = {"failed_attempt": attempt, "error": str(exc), "checkpointed": True}
                    self.repository.add_checkpoint(mission_id, task_id, {"agent": node.name, "attempt": attempt, "error": str(exc), "shared_state": shared_state})
                    await asyncio.sleep(0.02)
                    continue
                self.repository.update_task(task_id, status="failed", error=str(exc), completed_at=utc_now(), latency_ms=latency_ms)
                self.repository.add_event(
                    mission_id, "agent.failed", node.name,
                    f"{self.agents[node.name].display_name} exhausted {max_attempts} attempt(s): {exc}",
                    {"task_id": task_id, "exception": type(exc).__name__},
                )
                raise
        raise last_error or RuntimeError(f"Agent {node.name} failed without an exception")

    def control(self, mission_id: str, action: str, actor: str, reason: str) -> dict[str, Any]:
        mission = self.repository.get_mission(mission_id)
        if not mission:
            raise ValueError("Mission not found")
        state_map = {"pause": "paused", "resume": "active", "stop": "stopped"}
        state = state_map[action]
        status = {"pause": "paused", "resume": "running", "stop": "stopped"}[action]
        self.repository.update_mission(mission_id, control_state=state, status=status)
        if action == "stop":
            self._stop_pending_tasks(mission_id, reason)
        self.repository.add_event(mission_id, f"control.{action}", actor, reason, {"control_state": state})
        return self.repository.get_mission(mission_id) or mission

    def _stop_pending_tasks(self, mission_id: str, reason: str) -> None:
        for task in self.repository.list_tasks(mission_id):
            if task["status"] in {"pending", "running", "retrying", "blocked"}:
                self.repository.update_task(task["id"], status="stopped", error=reason, completed_at=utc_now())

    @staticmethod
    def _estimate_tokens(payload: Any) -> int:
        return max(1, len(json.dumps(payload, default=str, ensure_ascii=False)) // 4)

    @staticmethod
    def _assert_budget_available(mission: dict[str, Any]) -> None:
        if mission.get("tokens_used", 0) >= mission.get("token_budget", 0):
            raise BudgetExceeded("Token budget exhausted before the next agent could start.")
        if mission.get("spent_usd", 0) >= mission.get("budget_usd", 0):
            raise BudgetExceeded("Cost budget exhausted before the next agent could start.")
