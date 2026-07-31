from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MissionStatus = Literal[
    "queued", "running", "paused", "awaiting_approval", "stopped",
    "completed", "failed", "budget_exceeded",
]
TaskStatus = Literal["pending", "running", "retrying", "completed", "failed", "blocked", "stopped"]
Role = Literal["viewer", "analyst", "risk_manager", "admin", "agent"]
ProofScenario = Literal[
    "standard", "prompt_injection", "unauthorized_tool", "high_risk_approval",
    "retry_recovery", "weak_report_repair", "budget_limit",
]


class MissionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    vendor_name: str = Field(min_length=2, max_length=120)
    objective: str = Field(min_length=10, max_length=4000)
    auto_run: bool = True
    budget_usd: float = Field(default=2.0, gt=0, le=1000)
    token_budget: int = Field(default=50_000, ge=100, le=10_000_000)
    require_approval_for_high_risk: bool = True
    proof_scenario: ProofScenario = "standard"
    idempotency_key: str | None = Field(default=None, max_length=160)


class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    mission_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=160)


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=6, ge=1, le=20)
    include_quarantined: bool = False


class ConnectorExecuteRequest(BaseModel):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    mission_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=160)


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)


class ControlAction(BaseModel):
    action: Literal["pause", "resume", "stop"]
    reason: str = Field(default="Operator control", max_length=500)


class ProofScenarioRequest(BaseModel):
    scenario: ProofScenario
