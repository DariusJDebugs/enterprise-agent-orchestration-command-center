# Phase 3 Operations Runbook

## Start and verify

1. Load the approved environment configuration.
2. Run `python scripts/migrate.py`.
3. Start Uvicorn or the production Compose deployment.
4. Confirm `/api/health` and `/api/readiness` return HTTP 200.
5. Load demonstration data only in non-production environments.

## Incident controls

- Pause a mission when human review is required.
- Stop a mission when authorization, cost or security boundaries are uncertain.
- Inspect Security, Tool Calls, Observability and Audit before resuming.
- Export the mission audit record for incident evidence.

## Recovery

Use `scripts/backup.py` before upgrades. For restore, stop writers, verify checksum, run `scripts/restore.py`, reapply migrations and verify readiness/audit integrity.

## Escalation

Do not bypass a high-risk approval gate. Do not re-enable quarantined content in ordinary RAG. Escalate identity, data-handling, connector and model-provider changes for customer-specific security review.
