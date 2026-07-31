#!/usr/bin/env python3
from __future__ import annotations

import compileall
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.main import create_app
from scripts.release_hygiene import scan as hygiene_scan

REQUIRED_FILES = [
    "Dockerfile", "docker-compose.production.yml", ".env.production.example", ".dockerignore", ".gitignore",
    "scripts/deploy.sh", "scripts/migrate.py", "scripts/backup.py", "scripts/restore.py",
    "scripts/release_hygiene.py", "docs/CHALLENGE_ALIGNMENT.md", "docs/ARCHITECTURE.md",
    "docs/architecture.svg", "docs/DEPLOYMENT_GUIDE.md", "docs/THREAT_MODEL.md", "docs/API_REFERENCE.md",
    "docs/MCP_GUIDE.md", "docs/REQUIREMENTS_EVIDENCE_MATRIX.md", "docs/ENTERPRISE_CASE_STUDY.md",
    "docs/DEMO_SCRIPT.md", "docs/CHALLENGE_PROPOSAL.md", "docs/EVALUATOR_QUICKSTART.md",
]


def public_command(command: list[str]) -> list[str]:
    normalized = list(command)
    if normalized and Path(normalized[0]).name.startswith("python"):
        normalized[0] = "python"
    return normalized


def run(command: list[str], log_path: Path) -> dict[str, object]:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    output = completed.stdout + completed.stderr
    output = output.replace(str(PROJECT_ROOT), ".")
    log_path.write_text(output, encoding="utf-8")
    return {"command": public_command(command), "returncode": completed.returncode, "passed": completed.returncode == 0}


def main() -> None:
    evidence = PROJECT_ROOT / "release_evidence"
    logs = evidence / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "python_requirement_satisfied": sys.version_info >= (3, 11),
        "platform": {"system": platform.system(), "machine": platform.machine()},
    }

    missing = [name for name in REQUIRED_FILES if not (PROJECT_ROOT / name).exists()]
    results["required_files"] = {"passed": not missing, "missing": missing, "count": len(REQUIRED_FILES)}

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.production.yml").read_text(encoding="utf-8"))
    service = compose["services"]["command-center"]
    docker_available = shutil.which("docker") is not None
    results["container_static_validation"] = {
        "passed": all([
            "USER 10001:10001" in dockerfile,
            "HEALTHCHECK" in dockerfile,
            service.get("read_only") is True,
            "ALL" in service.get("cap_drop", []),
            "no-new-privileges:true" in service.get("security_opt", []),
            bool(service.get("secrets")),
        ]),
        "non_root": "USER 10001:10001" in dockerfile,
        "read_only_root": service.get("read_only") is True,
        "capabilities_dropped": "ALL" in service.get("cap_drop", []),
        "secret_mount": bool(service.get("secrets")),
        "docker_engine_available": docker_available,
    }

    results["compileall"] = {"passed": compileall.compile_dir(str(PROJECT_ROOT / "app"), quiet=1) and compileall.compile_dir(str(PROJECT_ROOT / "scripts"), quiet=1)}
    results["javascript"] = run(["node", "--check", "app/static/app.js"], logs / "javascript_syntax.log")
    results["pytest"] = run([sys.executable, "-m", "pytest", "-q"], logs / "pytest.log")
    results["phase3_self_test"] = run([sys.executable, "scripts/run_phase3_self_test.py"], logs / "phase3_selftest.log")

    with tempfile.TemporaryDirectory(prefix="eacc-verification-") as temp:
        root = Path(temp)
        settings = Settings(
            database_path=root / "verify.db", upload_dir=root / "uploads", backup_dir=root / "backups",
            app_environment="verification", json_logs=False, agent_step_delay_ms=0,
        )
        with TestClient(create_app(settings)) as client:
            health = client.get("/api/health")
            readiness = client.get("/api/readiness")
            openapi = client.get("/openapi.json")
            mcp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            (evidence / "openapi.json").write_text(json.dumps(openapi.json(), indent=2), encoding="utf-8")
            readiness_payload = readiness.json()
            readiness_payload["directories"] = {key: bool(value) for key, value in readiness_payload.get("directories", {}).items()}
            results["runtime_smoke"] = {
                "passed": health.status_code == 200 and readiness.status_code == 200 and mcp.status_code == 200,
                "health": health.json(),
                "readiness": readiness_payload,
                "mcp_tool_count": len(mcp.json()["result"]["tools"]),
                "openapi_path_count": len(openapi.json()["paths"]),
            }

    results["mcp_sdk"] = {
        "dependency_declared": "mcp" in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8"),
        "sdk_importable_in_validation_environment": importlib.util.find_spec("mcp") is not None,
        "http_jsonrpc_contract_tested": True,
    }
    hygiene = hygiene_scan()
    results["github_hygiene"] = hygiene

    critical = [
        results["python_requirement_satisfied"], results["required_files"]["passed"],
        results["container_static_validation"]["passed"], results["compileall"]["passed"],
        results["javascript"]["passed"], results["pytest"]["passed"],
        results["phase3_self_test"]["passed"], results["runtime_smoke"]["passed"], hygiene["status"] == "PASS",
    ]
    results["status"] = "PASS" if all(critical) else "FAIL"
    (evidence / "GITHUB_HYGIENE_SCAN.json").write_text(json.dumps(hygiene, indent=2), encoding="utf-8")
    (evidence / "PHASE3_VERIFICATION.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
