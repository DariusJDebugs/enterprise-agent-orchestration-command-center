# Evaluator Quickstart

## 1. Understand the project in five minutes

Read, in order:

1. `README.md`
2. `docs/CHALLENGE_ALIGNMENT.md`
3. `docs/REQUIREMENTS_EVIDENCE_MATRIX.md`
4. `docs/ARCHITECTURE.md`
5. `docs/TEST_RESULTS_REPORT.md`

This establishes the project origin, requirements-driven workflow, system design, proof map, and honest maturity boundary.

## 2. Run verification

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
mkdir -p secrets
python scripts/generate_secret.py --output secrets/audit_hmac_secret
python scripts/migrate.py
python -m pytest -q
python scripts/run_phase3_self_test.py
python scripts/release_hygiene.py --check
python scripts/verify_release.py
```

Expected result:

- `32 passed`
- `PHASE 3 SELF-TEST PASS`
- `RELEASE HYGIENE PASS`
- release verification status `PASS`

## 3. Launch the application

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open:

- `/` — Command Center
- `/docs` — interactive OpenAPI
- `/api/health` — liveness and runtime inventory
- `/api/readiness` — database/schema/configuration readiness

## 4. Demonstrate the standard mission

1. Select **Load demonstration data**.
2. Select **New vendor review** and launch the default Northstar Cloud Systems scenario.
3. Inspect the eleven-agent workflow from coordinator through final report.
4. Open Messages, Tool Calls, Observability, Audit, and Final Report.
5. Confirm stable `DOC-…#CHUNK-…` citations and a valid audit chain.

## 5. Demonstrate governance and security

Open **Governance lab** and run:

- prompt-injection quarantine;
- high-risk human approval;
- unauthorized tool denial;
- retry recovery;
- weak-report repair;
- budget stop;
- pause/resume/stop.

Each scenario persists real mission, event, trace, metric, approval, incident, tool-call, and audit evidence.

## 6. Inspect deployment evidence

Review:

- `Dockerfile`
- `docker-compose.production.yml`
- `.dockerignore`
- `.env.production.example`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/SECURE_CONFIGURATION.md`
- `docs/BACKUP_RECOVERY.md`
- `release_evidence/PHASE3_VERIFICATION.json`

Live Docker execution is environment-dependent; the repository does not claim it where Docker Engine was unavailable.
