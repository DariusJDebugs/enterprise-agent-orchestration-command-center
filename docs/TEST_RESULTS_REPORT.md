# Final Test Results Report

## Status: PASS

Validation date: 2026-07-31  
Runtime: Python 3.13.5  
Declared runtime: Python 3.11+

| Validation | Result |
|---|---|
| Automated tests | 32 passed |
| Full Phase 3 self-test | PASS |
| Governance/adversarial proofs | 7/7 passed |
| Python compilation | PASS |
| Frontend JavaScript syntax | PASS |
| Liveness endpoint | PASS |
| Readiness endpoint | PASS |
| Database integrity | `ok` |
| Schema migration | version 3 applied |
| OpenAPI export | 27 paths |
| MCP JSON-RPC | 5 tools listed; contract tests passed |
| Backup/restore | checksum and integrity-verified round trip passed |
| Audit chain | valid; 36 records in standard mission |
| Standard mission | 11 tasks, 11 traces, 34 metrics, 8 citations |
| Container hardening configuration | static validation passed |
| GitHub release-hygiene scan | PASS; no findings |
| Live Docker image build | not executed; Docker Engine unavailable in validation environment |

## Proof scenarios

Prompt injection blocked; unauthorized tool denied; high-risk human approval; failed-agent retry recovery; weak-report rejection and repair; budget stop; persistent pause/resume/stop.

Machine-readable evidence is in `release_evidence/PHASE3_VERIFICATION.json` and `SELF_TEST_REPORT.json`.

## GitHub publication checks

The final source tree was scanned for private filesystem paths, personal identifiers, common credential patterns, forbidden runtime artifacts, oversized release media, stale interface claims, and missing publication documents. The final scan passed with no findings. Large video and verbose evidence are separated into GitHub Release assets.
