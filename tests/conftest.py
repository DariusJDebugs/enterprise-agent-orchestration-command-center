from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "test.db",
        upload_dir=tmp_path / "uploads",
        backup_dir=tmp_path / "backups",
        app_environment="test",
        json_logs=False,
        embedding_dimensions=128,
        chunk_size=500,
        chunk_overlap=70,
        top_k_retrieval=6,
        agent_step_delay_ms=0,
        llm_mode="deterministic",
    )


@pytest.fixture()
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
