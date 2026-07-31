from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from datetime import datetime, timezone


SCHEMA_VERSION = 3


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    checksum TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    trust_state TEXT NOT NULL DEFAULT 'untrusted',
    security_status TEXT NOT NULL DEFAULT 'clean',
    security_findings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(document_id, chunk_index),
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    vendor_name TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'unknown',
    context_json TEXT NOT NULL DEFAULT '{}',
    final_report TEXT,
    owner_role TEXT NOT NULL DEFAULT 'analyst',
    control_state TEXT NOT NULL DEFAULT 'active',
    budget_usd REAL NOT NULL DEFAULT 2.0,
    token_budget INTEGER NOT NULL DEFAULT 50000,
    spent_usd REAL NOT NULL DEFAULT 0,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    approval_policy TEXT NOT NULL DEFAULT 'high_and_critical',
    proof_scenario TEXT NOT NULL DEFAULT 'standard',
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    dependencies_json TEXT NOT NULL,
    input_json TEXT NOT NULL DEFAULT '{}',
    output_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    token_usage INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0,
    trace_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    task_id TEXT,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    status TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    actor_role TEXT NOT NULL DEFAULT 'agent',
    permission_decision TEXT NOT NULL DEFAULT 'allowed',
    risk_level TEXT NOT NULL DEFAULT 'low',
    latency_ms REAL NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    decided_by TEXT,
    decision_note TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS security_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT,
    document_id INTEGER,
    incident_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    task_id TEXT,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    trace_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    input_json TEXT NOT NULL DEFAULT '{}',
    output_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    latency_ms REAL NOT NULL DEFAULT 0,
    token_usage INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    task_id TEXT,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    dimensions_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    task_id TEXT,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT,
    sequence INTEGER NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    category TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_tasks_mission ON tasks(mission_id);
CREATE INDEX IF NOT EXISTS idx_events_mission_id ON events(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_mission ON messages(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_mission ON tool_calls(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_approvals_mission ON approvals(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_security_mission ON security_incidents(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_traces_mission ON traces(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_metrics_mission ON metrics(mission_id, id);
CREATE INDEX IF NOT EXISTS idx_audit_mission ON audit_log(mission_id, id);
"""


MIGRATIONS: dict[str, dict[str, str]] = {
    "documents": {
        "trust_state": "TEXT NOT NULL DEFAULT 'untrusted'",
        "security_status": "TEXT NOT NULL DEFAULT 'clean'",
        "security_findings_json": "TEXT NOT NULL DEFAULT '[]'",
    },
    "missions": {
        "owner_role": "TEXT NOT NULL DEFAULT 'analyst'",
        "control_state": "TEXT NOT NULL DEFAULT 'active'",
        "budget_usd": "REAL NOT NULL DEFAULT 2.0",
        "token_budget": "INTEGER NOT NULL DEFAULT 50000",
        "spent_usd": "REAL NOT NULL DEFAULT 0",
        "tokens_used": "INTEGER NOT NULL DEFAULT 0",
        "approval_policy": "TEXT NOT NULL DEFAULT 'high_and_critical'",
        "proof_scenario": "TEXT NOT NULL DEFAULT 'standard'",
        "idempotency_key": "TEXT",
    },
    "tasks": {
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 3",
        "token_usage": "INTEGER NOT NULL DEFAULT 0",
        "cost_usd": "REAL NOT NULL DEFAULT 0",
        "latency_ms": "REAL NOT NULL DEFAULT 0",
        "trace_json": "TEXT NOT NULL DEFAULT '{}'",
        "idempotency_key": "TEXT",
    },
    "tool_calls": {
        "actor": "TEXT NOT NULL DEFAULT 'system'",
        "actor_role": "TEXT NOT NULL DEFAULT 'agent'",
        "permission_decision": "TEXT NOT NULL DEFAULT 'allowed'",
        "risk_level": "TEXT NOT NULL DEFAULT 'low'",
        "latency_ms": "REAL NOT NULL DEFAULT 0",
        "cost_usd": "REAL NOT NULL DEFAULT 0",
        "idempotency_key": "TEXT",
    },
}


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.RLock()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _configure_journal(self, conn: sqlite3.Connection) -> None:
        # SQLite WAL is unreliable on Windows-mounted WSL paths. Automatically
        # choose DELETE there, WAL elsewhere, and fall back safely.
        mode = "DELETE" if self.path.startswith("/mnt/") else "WAL"
        try:
            conn.execute(f"PRAGMA journal_mode={mode}")
        except sqlite3.OperationalError:
            conn.execute("PRAGMA journal_mode=DELETE")

    def initialize(self) -> None:
        with self._lock, self.connect() as conn:
            self._configure_journal(conn)
            conn.executescript(SCHEMA)
            for table, columns in MIGRATIONS.items():
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                for column, definition in columns.items():
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, description, applied_at) VALUES (?, ?, ?)",
                (SCHEMA_VERSION, "Phase 3 enterprise deployment schema baseline", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def check(self) -> dict[str, object]:
        with self._lock, self.connect() as conn:
            ping = conn.execute("SELECT 1").fetchone()[0]
            integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
        return {
            "reachable": ping == 1,
            "integrity": integrity,
            "journal_mode": journal,
            "schema_version": max(versions, default=0),
            "expected_schema_version": SCHEMA_VERSION,
        }

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(sql, params)
            return int(cursor.lastrowid or 0)

    def executemany(self, sql: str, params: list[tuple]) -> None:
        with self.transaction() as conn:
            conn.executemany(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock, self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock, self.connect() as conn:
            return list(conn.execute(sql, params).fetchall())
