# Historical Phase 2 Requirement-to-Evidence Matrix

> Historical validation snapshot. Current release results are in `TEST_RESULTS_REPORT.md`.

| Requirement | Runtime evidence | Automated evidence |
|---|---|---|
| Human approval gates | `approvals`, `awaiting_approval`, approve/reject API and UI | High-risk approval and rejection tests |
| RBAC | `X-Role`, `GovernanceEngine`, protected write/control endpoints | Viewer mutation-denial tests |
| Agent/tool permissions | Named-agent and human-role allowlists | Unauthorized tool denial tests |
| Risk classification | Reviewer composite score and four risk levels | Standard and forced-high-risk missions |
| Prompt injection | Ingestion scanner and security findings | Malicious document quarantine test |
| Untrusted isolation | Quarantined metadata and safe-search filtering | Normal vs forensic retrieval test |
| Unauthorized blocking | Denied tool call plus security incident | Viewer and wrong-agent tests |
| Budgets | Token/cost counters and `budget_exceeded` | Budget proof mission |
| Pause/stop | Persistent `control_state` and endpoints | Async pause/resume and stop tests |
| Execution traces | `traces` table and UI | Trace-count assertions |
| Prompt/response/tool records | Agent trace inputs/outputs and detailed tool calls | End-to-end mission assertions |
| Cost/latency monitoring | `metrics`, task/tool latency and cost | Metric assertions |
| Groundedness | `EvaluationService.groundedness` | Final quality-gate assertion |
| Citation validation | Stable `DOC-id#CHUNK-n` resolution | Safe citation tests |
| Reviewer/red team | Reviewer → draft → red-team → report graph | Weak-draft rejection/repair test |
| Recovery | Checkpoint plus retry state | Simulated transient operations failure |
| Idempotency | Mission and tool idempotency keys | Duplicate mission test |
| Audit | HMAC-linked audit chain and export | Verification/export tests |
| Adversarial test suite | 23 pytest tests | `pytest -q` |
| Full self-test | Seven control proofs in a disposable environment | `python scripts/run_self_test.py` |

## Packaged validation result

- 23 tests passed
- 11 agent tasks completed in a standard mission
- 11 traces and 34 metrics persisted
- 36 standard-mission audit records verified
- 8 report citations generated in the self-test
