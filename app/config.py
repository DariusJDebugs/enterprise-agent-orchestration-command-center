from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_TRUE = {"1", "true", "yes", "on"}


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in _TRUE


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.getenv(name, default).split(",") if part.strip())


def _secret_env(name: str, default: str = "") -> str:
    file_value = os.getenv(f"{name}_FILE", "").strip()
    if file_value:
        return Path(file_value).read_text(encoding="utf-8").strip()
    return os.getenv(name, default)


@dataclass(slots=True)
class Settings:
    app_name: str = "Enterprise Agent Orchestration Command Center"
    app_version: str = "3.0.0"
    app_environment: str = "development"
    build_commit: str = "local"
    database_path: Path = Path("data/command_center.db")
    upload_dir: Path = Path("data/uploads")
    backup_dir: Path = Path("data/backups")
    embedding_dimensions: int = 192
    chunk_size: int = 900
    chunk_overlap: int = 150
    top_k_retrieval: int = 6
    agent_step_delay_ms: int = 100
    llm_mode: str = "deterministic"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    default_budget_usd: float = 2.0
    default_token_budget: int = 50_000
    max_agent_retries: int = 2
    approval_risk_levels: tuple[str, ...] = ("high", "critical")
    audit_hmac_secret: str = "local-development-audit-secret"
    log_level: str = "INFO"
    json_logs: bool = True
    trusted_hosts: tuple[str, ...] = ("*",)
    allowed_origins: tuple[str, ...] = ()
    enforce_secure_config: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "development").strip().lower()
        return cls(
            app_version=os.getenv("APP_VERSION", "3.0.0"),
            app_environment=environment,
            build_commit=os.getenv("BUILD_COMMIT", "local"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/command_center.db")),
            upload_dir=Path(os.getenv("UPLOAD_DIR", "data/uploads")),
            backup_dir=Path(os.getenv("BACKUP_DIR", "data/backups")),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "192")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "900")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "150")),
            top_k_retrieval=int(os.getenv("TOP_K_RETRIEVAL", "6")),
            agent_step_delay_ms=int(os.getenv("AGENT_STEP_DELAY_MS", "100")),
            llm_mode=os.getenv("LLM_MODE", "deterministic"),
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_api_key=_secret_env("LLM_API_KEY"),
            llm_model=os.getenv("LLM_MODEL", ""),
            default_budget_usd=float(os.getenv("DEFAULT_BUDGET_USD", "2.0")),
            default_token_budget=int(os.getenv("DEFAULT_TOKEN_BUDGET", "50000")),
            max_agent_retries=int(os.getenv("MAX_AGENT_RETRIES", "2")),
            approval_risk_levels=_csv_env("APPROVAL_RISK_LEVELS", "high,critical"),
            audit_hmac_secret=_secret_env("AUDIT_HMAC_SECRET", "local-development-audit-secret"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            json_logs=_bool_env("JSON_LOGS", True),
            trusted_hosts=_csv_env("TRUSTED_HOSTS", "*"),
            allowed_origins=_csv_env("ALLOWED_ORIGINS", ""),
            enforce_secure_config=_bool_env("ENFORCE_SECURE_CONFIG", environment == "production"),
        )

    @property
    def is_production(self) -> bool:
        return self.app_environment == "production"

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def security_findings(self) -> list[str]:
        findings: list[str] = []
        weak_secrets = {"", "local-development-audit-secret", "replace-with-a-long-random-secret-for-non-demo-use", "replace-me"}
        if self.audit_hmac_secret in weak_secrets or len(self.audit_hmac_secret) < 32:
            findings.append("AUDIT_HMAC_SECRET must be a unique random value of at least 32 characters")
        if self.llm_mode == "openai-compatible":
            if not self.llm_base_url:
                findings.append("LLM_BASE_URL is required for openai-compatible mode")
            if not self.llm_model:
                findings.append("LLM_MODEL is required for openai-compatible mode")
            if not self.llm_api_key:
                findings.append("LLM_API_KEY is required for openai-compatible mode")
        if self.is_production and self.trusted_hosts == ("*",):
            findings.append("TRUSTED_HOSTS must be restricted in production")
        return findings

    def validate_startup(self) -> None:
        findings = self.security_findings()
        if self.enforce_secure_config and findings:
            raise RuntimeError("Secure configuration validation failed: " + "; ".join(findings))
