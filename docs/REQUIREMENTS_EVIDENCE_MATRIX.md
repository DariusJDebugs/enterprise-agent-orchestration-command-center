# Requirements-to-Evidence Matrix

This matrix connects the published solution requirements to implementation, automated validation, and evaluator-visible evidence.

| Requested capability | Working implementation | Automated validation | Evaluator evidence |
|---|---|---|---|
| Multi-agent architecture/orchestration | 11-agent persistent dependency graph with layered execution | `tests/test_orchestrator.py` | UI Agent Workflow; `/api/architecture`; `app/orchestrator.py` |
| Agent framework or comparable technology | typed custom graph runtime with dependencies, checkpoints, retry, gates, and idempotency | graph validation, retry, and duplicate-mission tests | architecture diagram and mission timeline |
| Prompt/context management | mission-scoped context, typed inputs/outputs, direct dependency context, messages, and traces | standard mission assertions | Messages and Observability tabs; `app/agents/` |
| RAG | ingestion, parsing, chunking, hybrid retrieval, citation generation, quarantine filtering | `tests/test_rag.py` | Knowledge & Security UI; `app/rag.py` |
| MCP | JSON-RPC endpoint plus optional FastMCP stdio adapter | `tests/test_mcp.py` | `/mcp`; `app/mcp_server.py`; MCP guide |
| Vector/embedding strategy | deterministic 192-dimensional embeddings persisted with chunks | `tests/test_embeddings.py` | `app/embeddings.py`; database schema |
| Python software development | FastAPI backend, domain services, operations scripts, and tests | full pytest/compile suite | source repository and CI |
| REST/enterprise integration | OpenAPI API, connector registry, permission-scoped tools | API, connector, and permission tests | Tool Calls UI; `app/connectors.py`; API reference |
| Workflow automation | mission creation, dependency scheduling, concurrent layers, approvals, controls, and event history | orchestration and control tests | mission timeline and task graph |
| Observability/evaluation/monitoring | traces, latency/token/cost metrics, groundedness, citation checks, reviewer/red-team gates | final quality-gate assertions | Observability tab; test report |
| Governance | RBAC, human/agent permissions, risk classification, budgets, audit | `tests/test_governance.py` | Governance Lab, Approval and Audit tabs |
| Human in the loop | persisted high-risk pause and authorized decision path | high-risk approval scenario | Approvals tab |
| Security/permission/injection mitigation | deny-by-policy calls, incident records, injection detection, quarantine, safe retrieval, secure startup gate | security/adversarial tests | Security tab; threat model |
| Enterprise deployment | non-root Docker, hardened Compose, migrations, health/readiness, logging, backup/restore | `tests/test_phase3.py`; release verifier | deployment guide and release evidence |
| Demonstrable software-engineering delivery | runnable source, 32 tests, 7 proof scenarios, case study, screenshots, demo, and verification | CI + self-test + hygiene scan | this repository and v3.0.0 release assets |

## Proof-chain convention

Every claim should be inspectable through:

```text
Requirement → architecture component → source path → automated test → evidence artifact → demonstration
```

The detailed challenge-origin and methodology explanation is in [`CHALLENGE_ALIGNMENT.md`](CHALLENGE_ALIGNMENT.md).
