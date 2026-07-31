#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 127; }
docker compose version >/dev/null
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE. Copy .env.production.example and configure secrets." >&2; exit 2; }

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

python3 - <<'PY'
from app.config import Settings
s = Settings.from_env()
s.validate_startup()
print("secure configuration: PASS")
PY

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --pull
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm command-center python scripts/migrate.py
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT:-8000}/api/readiness" >/dev/null; then
    echo "deployment ready"
    exit 0
  fi
  sleep 2
done

echo "readiness check timed out" >&2
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=200
exit 1
