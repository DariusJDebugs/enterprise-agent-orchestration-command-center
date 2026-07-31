from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.database import SCHEMA_VERSION, Database
from app.operations import create_database_backup, restore_database_backup


def test_phase3_health_version_and_security_headers(client):
    response = client.get("/api/health", headers={"X-Request-ID": "phase3-test-request"})
    assert response.status_code == 200
    assert response.json()["phase"] == 3
    assert response.json()["version"] == "3.0.0"
    assert response.headers["x-request-id"] == "phase3-test-request"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_readiness_checks_database_schema_and_directories(client):
    response = client.get("/api/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database"]["integrity"] == "ok"
    assert payload["database"]["schema_version"] == SCHEMA_VERSION
    assert all(payload["directories"].values())


def test_version_and_enterprise_requirement_evidence(client):
    assert client.get("/api/version").json()["python_requirement"] == ">=3.11"
    matrix = client.get("/api/requirements").json()
    assert matrix["status"] == "enterprise pilot-ready beta"
    names = {row["requirement"] for row in matrix["requirements"]}
    assert "Enterprise deployment" in names
    assert "MCP and REST integrations" in names


def test_schema_migration_record(settings):
    database = Database(settings.database_path)
    status = database.check()
    assert status["schema_version"] == SCHEMA_VERSION
    assert status["expected_schema_version"] == SCHEMA_VERSION


def test_backup_restore_round_trip(settings):
    database = Database(settings.database_path)
    database.execute("CREATE TABLE IF NOT EXISTS phase3_backup_proof(value TEXT)")
    database.execute("INSERT INTO phase3_backup_proof(value) VALUES (?)", ("evidence",))
    manifest = create_database_backup(settings.database_path, settings.backup_dir, "pytest")
    restored = settings.database_path.parent / "restored.db"
    result = restore_database_backup(Path(str(manifest["backup"])), restored, str(manifest["sha256"]))
    restored_db = Database(restored)
    assert restored_db.fetchone("SELECT value FROM phase3_backup_proof")[0] == "evidence"
    assert result["sha256"] == manifest["sha256"]


def test_backup_restore_rejects_bad_checksum(settings):
    Database(settings.database_path)
    manifest = create_database_backup(settings.database_path, settings.backup_dir, "checksum")
    with pytest.raises(ValueError, match="checksum"):
        restore_database_backup(Path(str(manifest["backup"])), settings.database_path.parent / "bad.db", "0" * 64)


def test_production_secure_configuration_gate(tmp_path):
    settings = Settings(
        database_path=tmp_path / "prod.db",
        upload_dir=tmp_path / "uploads",
        backup_dir=tmp_path / "backups",
        app_environment="production",
        enforce_secure_config=True,
        trusted_hosts=("*",),
        audit_hmac_secret="weak",
    )
    with pytest.raises(RuntimeError, match="Secure configuration"):
        settings.validate_startup()


def test_secret_file_loading(monkeypatch, tmp_path):
    secret = tmp_path / "audit_secret"
    secret.write_text("x" * 64, encoding="utf-8")
    monkeypatch.setenv("AUDIT_HMAC_SECRET_FILE", str(secret))
    monkeypatch.delenv("AUDIT_HMAC_SECRET", raising=False)
    assert Settings.from_env().audit_hmac_secret == "x" * 64


def test_openapi_contains_operational_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/health" in paths
    assert "/api/readiness" in paths
    assert "/api/version" in paths
    assert "/mcp" in paths
