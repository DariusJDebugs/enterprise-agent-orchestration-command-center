# Deployment Guide

## Supported modes

- **Evaluator/local:** Python 3.11+ and deterministic provider mode.
- **Container pilot:** Docker Compose, non-root runtime user, persistent data volume, secret file, restricted host/origin configuration and readiness probe.

## Local launch

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python scripts/migrate.py
python -m pytest -q
python scripts/run_phase3_self_test.py
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open `/`, `/docs`, `/api/health` and `/api/readiness` on port 8000.

## Production-style Compose pilot

```bash
cp .env.production.example .env.production
mkdir -p secrets
python scripts/generate_secret.py --output secrets/audit_hmac_secret
# Edit TRUSTED_HOSTS and ALLOWED_ORIGINS in .env.production.
COMPOSE_FILE=docker-compose.production.yml ENV_FILE=.env.production ./scripts/deploy.sh
```

The deployment script validates secure configuration, validates the Compose model, builds the image, applies migrations, starts the service and waits for readiness.

## Container hardening included

- unprivileged UID/GID 10001
- read-only root filesystem in production Compose
- all Linux capabilities dropped
- `no-new-privileges`
- secret mounted as a file rather than committed to source
- local-only default port binding, intended to sit behind an approved TLS reverse proxy
- persistent named volume for database, uploads and backups
- liveness/readiness checks and graceful SIGTERM handling

## External controls still required for a real customer production deployment

TLS termination, enterprise identity/SSO, central secret manager, centralized logs, vulnerability scanning, external penetration testing, backup retention, disaster-recovery objectives and customer-specific connector approval must be configured in the target environment.
