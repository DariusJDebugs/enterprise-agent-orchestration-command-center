# Threat Model

## Assets

Enterprise documents, mission context, tool permissions, external credentials, reports, approval decisions, audit records and operational availability.

| Threat | Implemented control | Residual risk / production action |
|---|---|---|
| Prompt injection in documents | detection, quarantine, exclusion from normal RAG, incident record | continuously tune detectors and add model/provider defenses |
| Unauthorized tool use | RBAC, agent/tool allowlists, denied-call persistence | integrate real IdP and least-privilege service identities |
| Approval bypass | risk classification and persisted human gate | enforce authenticated approver identity and separation of duties |
| Secret exposure | no embedded production keys, file-based secret support, redaction-oriented logs | use customer secret manager and rotate credentials |
| Audit tampering | HMAC-linked records and verification/export | forward to immutable centralized storage |
| Malicious/oversized upload | filename sanitization, 20 MB limit, trust state and parsing controls | malware scanning and content-disarm pipeline |
| Hallucinated or weak report | groundedness, citation validation, reviewer and red-team gate | validate with live provider models and domain experts |
| Runaway cost/actions | token/cost budgets, pause/resume/stop | provider-side quotas and external circuit breakers |
| Worker/process failure | checkpoints, bounded retry, idempotency | distributed queue and high-availability design if required |
| Database corruption/loss | integrity checks and verified backup/restore | encrypted off-host backups and scheduled restore drills |
| Host-header/CORS abuse | TrustedHost and allowlisted origins | TLS reverse proxy and security-header policy review |
| Container privilege escalation | non-root user, capabilities dropped, read-only root, no-new-privileges | image scanning, signed images and hardened orchestration platform |

## Trust boundaries

Browser ↔ API; API ↔ orchestrator; orchestrator ↔ tools/connectors; ingestion ↔ RAG; application ↔ SQLite; application ↔ optional external model provider; container ↔ host/volume.

## Honest residual boundary

This package contains defensible controls and adversarial tests, but it is not a substitute for customer-specific architecture review, penetration testing, legal/privacy assessment or formal certification.
