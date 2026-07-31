# Enterprise Agent Orchestration Command Center — Architecture

## Purpose

The system demonstrates a governed enterprise vendor-risk workflow in which **eleven governed agents** coordinate through a persistent dependency graph. It is designed as a controlled single-tenant pilot-ready beta and as inspectable software-engineering evidence for enterprise AI-agent orchestration work.

## Runtime layers

1. **Experience layer:** browser command center, mission controls, approval queue, security events, traces, metrics, audit, and reports.
2. **API layer:** FastAPI/OpenAPI, role-aware endpoints, MCP JSON-RPC, and an optional FastMCP stdio adapter.
3. **Orchestration layer:** coordinator, knowledge, vendor intelligence, security, compliance, finance, operations, reviewer, draft report, red team, and final report agents.
4. **Knowledge/tool layer:** document ingestion, deterministic embeddings, hybrid retrieval, stable citations, connector registry, and permission-scoped tools.
5. **Governance layer:** RBAC, allowlists, risk classification, approval gates, budgets, pause/resume/stop, and prompt-injection quarantine.
6. **Assurance layer:** traces, metrics, groundedness, citation checks, adversarial report review, retry, idempotency, checkpoints, and an HMAC-linked audit chain.
7. **Operations layer:** versioned schema baseline, liveness/readiness, structured JSON logging, non-root container, secure secret files, and integrity-checked backup/restore.

## Agent dependency graph

The coordinator creates ten governed downstream workstreams. Knowledge and vendor intelligence execute first; security, compliance, finance, and operations use their evidence; the independent reviewer produces the risk posture; the draft report is challenged by the red-team agent; and the final report is emitted only after quality gates pass.

## Data boundaries

- SQLite is the durable system of record for missions, tasks, messages, tool calls, approvals, incidents, traces, metrics, checkpoints, and audit records.
- Uploaded documents remain local to the configured upload directory.
- Quarantined content is retained for forensic inspection but excluded from ordinary retrieval.
- Provider mode is deterministic/offline by default. An approved OpenAI-compatible endpoint is optional and configured externally.
- Liveness output intentionally avoids exposing host-specific filesystem paths.

## Deployment boundary

The release is a **single-tenant Enterprise Pilot-Ready / Challenge-Submission-Ready Beta**. It does not claim multi-region availability, distributed execution, production SSO, multitenancy, formal regulatory certification, or an external penetration-test attestation. Those are customer-specific productionization activities.
