from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..evaluation import EvaluationService
from ..llm import LLMProvider
from ..repository import Repository
from ..tools import ToolRegistry


@dataclass(slots=True)
class AgentResult:
    summary: str
    findings: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.75
    messages: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "findings": self.findings,
            "data": self.data,
            "citations": self.citations,
            "confidence": round(max(0.0, min(1.0, self.confidence)), 3),
            "messages": self.messages,
        }


@dataclass(slots=True)
class AgentContext:
    mission: dict[str, Any]
    task: dict[str, Any]
    upstream: dict[str, dict[str, Any]]
    shared_state: dict[str, Any]
    tools: ToolRegistry
    repository: Repository
    llm: LLMProvider
    evaluation: EvaluationService
    attempt: int = 1

    async def call_tool(self, name: str, arguments: dict[str, Any], *, approved: bool = False) -> dict[str, Any]:
        return await self.tools.call(
            name, arguments,
            actor=self.task["agent_name"], actor_role="agent",
            mission_id=self.mission["id"], task_id=self.task["id"], approved=approved,
            idempotency_key=f"{self.task['id']}:{name}:{self.attempt}",
        )


class BaseAgent:
    name = "base"
    display_name = "Base Agent"
    system_prompt = "Perform the assigned enterprise analysis and preserve evidence traceability."

    async def execute(self, context: AgentContext) -> AgentResult:
        raise NotImplementedError

    @staticmethod
    def upstream_output(context: AgentContext, agent_name: str) -> dict[str, Any]:
        return context.upstream.get(agent_name, {})

    @staticmethod
    def citations_from_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations = []
        seen: set[str] = set()
        for match in matches:
            label = str(match.get("citation", ""))
            if not label or label in seen:
                continue
            seen.add(label)
            citations.append({
                "citation": label,
                "document_name": match.get("document_name", "Unknown document"),
                "score": match.get("score", 0),
                "excerpt": str(match.get("content", ""))[:260],
            })
        return citations
