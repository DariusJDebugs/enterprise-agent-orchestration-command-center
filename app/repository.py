from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from .database import Database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def decode_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class Repository:
    def __init__(self, db: Database, audit_secret: str = "local-development-audit-secret"):
        self.db = db
        self.audit_secret = audit_secret.encode("utf-8")

    # Documents -----------------------------------------------------------------
    def create_document(
        self,
        *,
        name: str,
        content_type: str,
        checksum: str,
        size_bytes: int,
        trust_state: str = "untrusted",
        security_status: str = "clean",
        security_findings: list[dict[str, Any]] | None = None,
    ) -> int:
        return self.db.execute(
            """INSERT INTO documents(name, content_type, checksum, size_bytes, trust_state,
               security_status, security_findings_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name, content_type, checksum, size_bytes, trust_state, security_status,
                json.dumps(security_findings or []), utc_now(),
            ),
        )

    def get_document_by_checksum(self, checksum: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM documents WHERE checksum = ?", (checksum,))
        return self._decode_document(row) if row else None

    def get_document(self, document_id: int) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        return self._decode_document(row) if row else None

    def _decode_document(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["security_findings"] = decode_json(item.pop("security_findings_json", "[]"), [])
        return item

    def list_documents(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT d.*, COUNT(c.id) AS chunk_count
               FROM documents d LEFT JOIN chunks c ON c.document_id=d.id
               GROUP BY d.id ORDER BY d.created_at DESC"""
        )
        return [self._decode_document(row) for row in rows]

    def create_chunks(self, rows: list[tuple]) -> None:
        self.db.executemany(
            """INSERT INTO chunks(document_id, chunk_index, content, vector_json, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )

    def list_chunks(self, include_quarantined: bool = False) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT c.*, d.name AS document_name, d.trust_state, d.security_status
               FROM chunks c JOIN documents d ON d.id=c.document_id
               ORDER BY c.document_id, c.chunk_index"""
        )
        result = []
        for row in rows:
            item = dict(row)
            item["vector"] = decode_json(item.pop("vector_json"), [])
            item["metadata"] = decode_json(item.pop("metadata_json"), {})
            if not include_quarantined and item["metadata"].get("quarantined"):
                continue
            result.append(item)
        return result

    # Missions ------------------------------------------------------------------
    def create_mission(self, mission: dict[str, Any]) -> None:
        now = utc_now()
        self.db.execute(
            """INSERT INTO missions(id, title, vendor_name, objective, status, risk_level,
               context_json, final_report, owner_role, control_state, budget_usd, token_budget,
               spent_usd, tokens_used, approval_policy, proof_scenario, idempotency_key, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mission["id"], mission["title"], mission["vendor_name"], mission["objective"],
                mission.get("status", "queued"), mission.get("risk_level", "unknown"),
                json.dumps(mission.get("context", {})), mission.get("final_report"),
                mission.get("owner_role", "analyst"), mission.get("control_state", "active"),
                float(mission.get("budget_usd", 2.0)), int(mission.get("token_budget", 50_000)),
                float(mission.get("spent_usd", 0)), int(mission.get("tokens_used", 0)),
                mission.get("approval_policy", "high_and_critical"), mission.get("proof_scenario", "standard"),
                mission.get("idempotency_key"), now, now,
            ),
        )

    def update_mission(self, mission_id: str, **updates: Any) -> None:
        allowed = {
            "status", "risk_level", "context_json", "final_report", "title", "objective", "vendor_name",
            "owner_role", "control_state", "budget_usd", "token_budget", "spent_usd", "tokens_used",
            "approval_policy", "proof_scenario", "idempotency_key",
        }
        pairs: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "context_json" and not isinstance(value, str):
                value = json.dumps(value)
            pairs.append(f"{key} = ?")
            values.append(value)
        if not pairs:
            return
        pairs.append("updated_at = ?")
        values.extend([utc_now(), mission_id])
        self.db.execute(f"UPDATE missions SET {', '.join(pairs)} WHERE id = ?", tuple(values))

    def increment_usage(self, mission_id: str, tokens: int, cost_usd: float) -> dict[str, Any]:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE missions SET tokens_used=tokens_used+?, spent_usd=spent_usd+?, updated_at=? WHERE id=?",
                (int(tokens), float(cost_usd), utc_now(), mission_id),
            )
        return self.get_mission(mission_id) or {}

    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM missions WHERE id = ?", (mission_id,))
        if not row:
            return None
        return self._decode_mission(row)

    def get_mission_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM missions WHERE idempotency_key = ?", (key,))
        return self._decode_mission(row) if row else None

    def _decode_mission(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["context"] = decode_json(item.pop("context_json"), {})
        return item

    def list_missions(self) -> list[dict[str, Any]]:
        return [self._decode_mission(row) for row in self.db.fetchall("SELECT * FROM missions ORDER BY created_at DESC")]

    # Tasks ---------------------------------------------------------------------
    def create_tasks(self, mission_id: str, tasks: list[dict[str, Any]]) -> None:
        rows = []
        for task in tasks:
            rows.append((
                task["id"], mission_id, task["agent_name"], task["title"], task.get("status", "pending"),
                json.dumps(task.get("dependencies", [])), json.dumps(task.get("input", {})), "{}", None,
                0, int(task.get("max_attempts", 3)), 0, 0.0, 0.0, "{}", task.get("idempotency_key"), None, None,
            ))
        self.db.executemany(
            """INSERT INTO tasks(id, mission_id, agent_name, title, status, dependencies_json,
               input_json, output_json, error, attempts, max_attempts, token_usage, cost_usd,
               latency_ms, trace_json, idempotency_key, started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )

    def update_task(self, task_id: str, **updates: Any) -> None:
        allowed = {
            "status", "output_json", "error", "started_at", "completed_at", "input_json", "attempts",
            "max_attempts", "token_usage", "cost_usd", "latency_ms", "trace_json", "idempotency_key",
        }
        pairs: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key in {"output_json", "input_json", "trace_json"} and not isinstance(value, str):
                value = json.dumps(value)
            pairs.append(f"{key} = ?")
            values.append(value)
        if pairs:
            values.append(task_id)
            self.db.execute(f"UPDATE tasks SET {', '.join(pairs)} WHERE id = ?", tuple(values))

    def _decode_task(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["dependencies"] = decode_json(item.pop("dependencies_json"), [])
        item["input"] = decode_json(item.pop("input_json"), {})
        item["output"] = decode_json(item.pop("output_json"), {})
        item["trace"] = decode_json(item.pop("trace_json", "{}"), {})
        return item

    def list_tasks(self, mission_id: str) -> list[dict[str, Any]]:
        return [self._decode_task(row) for row in self.db.fetchall(
            "SELECT * FROM tasks WHERE mission_id = ? ORDER BY rowid", (mission_id,)
        )]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return self._decode_task(row) if row else None

    # Events/messages/tool calls ------------------------------------------------
    def add_event(self, mission_id: str, event_type: str, actor: str, message: str, payload: dict[str, Any] | None = None) -> int:
        event_id = self.db.execute(
            "INSERT INTO events(mission_id, event_type, actor, message, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mission_id, event_type, actor, message, json.dumps(payload or {}), utc_now()),
        )
        self.add_audit(mission_id, "event", actor, event_type, "recorded", {"event_id": event_id, "message": message, **(payload or {})})
        return event_id

    def list_events(self, mission_id: str, after_id: int = 0) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM events WHERE mission_id = ? AND id > ? ORDER BY id", (mission_id, after_id),
        )
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = decode_json(item.pop("payload_json"), {})
            result.append(item)
        return result

    def add_message(self, mission_id: str, sender: str, recipient: str, content: str, metadata: dict[str, Any] | None = None) -> int:
        return self.db.execute(
            "INSERT INTO messages(mission_id, sender, recipient, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mission_id, sender, recipient, content, json.dumps(metadata or {}), utc_now()),
        )

    def list_messages(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT * FROM messages WHERE mission_id = ? ORDER BY id", (mission_id,))
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = decode_json(item.pop("metadata_json"), {})
            result.append(item)
        return result

    def add_tool_call(
        self,
        mission_id: str,
        task_id: str | None,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        status: str = "completed",
        *,
        actor: str = "system",
        actor_role: str = "agent",
        permission_decision: str = "allowed",
        risk_level: str = "low",
        latency_ms: float = 0,
        cost_usd: float = 0,
        idempotency_key: str | None = None,
    ) -> int:
        call_id = self.db.execute(
            """INSERT INTO tool_calls(mission_id, task_id, tool_name, arguments_json, result_json, status,
               actor, actor_role, permission_decision, risk_level, latency_ms, cost_usd, idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mission_id, task_id, tool_name, json.dumps(arguments), json.dumps(result), status,
                actor, actor_role, permission_decision, risk_level, float(latency_ms), float(cost_usd),
                idempotency_key, utc_now(),
            ),
        )
        self.add_audit(mission_id, "tool", actor, tool_name, status, {
            "tool_call_id": call_id, "role": actor_role, "permission": permission_decision,
            "risk_level": risk_level, "idempotency_key": idempotency_key,
        })
        return call_id

    def list_tool_calls(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT * FROM tool_calls WHERE mission_id = ? ORDER BY id", (mission_id,))
        result = []
        for row in rows:
            item = dict(row)
            item["arguments"] = decode_json(item.pop("arguments_json"), {})
            item["result"] = decode_json(item.pop("result_json"), {})
            result.append(item)
        return result

    # Approvals -----------------------------------------------------------------
    def create_approval(self, mission_id: str, action_type: str, requested_by: str, risk_level: str, reason: str, payload: dict[str, Any]) -> int:
        existing = self.db.fetchone(
            "SELECT id FROM approvals WHERE mission_id=? AND action_type=? AND status='pending' ORDER BY id DESC LIMIT 1",
            (mission_id, action_type),
        )
        if existing:
            return int(existing["id"])
        approval_id = self.db.execute(
            """INSERT INTO approvals(mission_id, action_type, requested_by, risk_level, status, reason,
               payload_json, created_at) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (mission_id, action_type, requested_by, risk_level, reason, json.dumps(payload), utc_now()),
        )
        self.add_audit(mission_id, "approval", requested_by, action_type, "pending", {"approval_id": approval_id, "risk_level": risk_level})
        return approval_id

    def decide_approval(self, approval_id: int, decision: str, decided_by: str, note: str) -> dict[str, Any]:
        now = utc_now()
        self.db.execute(
            "UPDATE approvals SET status=?, decided_by=?, decision_note=?, decided_at=? WHERE id=? AND status='pending'",
            (decision, decided_by, note, now, approval_id),
        )
        approval = self.get_approval(approval_id)
        if approval:
            self.add_audit(approval["mission_id"], "approval", decided_by, approval["action_type"], decision, {"approval_id": approval_id, "note": note})
        return approval or {}

    def get_approval(self, approval_id: int) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM approvals WHERE id=?", (approval_id,))
        return self._decode_approval(row) if row else None

    def list_approvals(self, mission_id: str) -> list[dict[str, Any]]:
        return [self._decode_approval(row) for row in self.db.fetchall(
            "SELECT * FROM approvals WHERE mission_id=? ORDER BY id", (mission_id,)
        )]

    def _decode_approval(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["payload"] = decode_json(item.pop("payload_json"), {})
        return item

    # Security ------------------------------------------------------------------
    def add_security_incident(
        self,
        *,
        incident_type: str,
        severity: str,
        status: str,
        details: dict[str, Any],
        mission_id: str | None = None,
        document_id: int | None = None,
    ) -> int:
        incident_id = self.db.execute(
            """INSERT INTO security_incidents(mission_id, document_id, incident_type, severity, status,
               details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mission_id, document_id, incident_type, severity, status, json.dumps(details), utc_now()),
        )
        self.add_audit(mission_id, "security", "security_guard", incident_type, status, {"incident_id": incident_id, "severity": severity, **details})
        return incident_id

    def list_security_incidents(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        if mission_id:
            rows = self.db.fetchall("SELECT * FROM security_incidents WHERE mission_id=? ORDER BY id", (mission_id,))
        else:
            rows = self.db.fetchall("SELECT * FROM security_incidents ORDER BY id DESC")
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = decode_json(item.pop("details_json"), {})
            result.append(item)
        return result

    # Traces, metrics, checkpoints ---------------------------------------------
    def add_trace(
        self,
        mission_id: str,
        task_id: str | None,
        span_id: str,
        trace_type: str,
        actor: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        status: str,
        *,
        parent_span_id: str | None = None,
        latency_ms: float = 0,
        token_usage: int = 0,
        cost_usd: float = 0,
    ) -> int:
        return self.db.execute(
            """INSERT INTO traces(mission_id, task_id, span_id, parent_span_id, trace_type, actor,
               input_json, output_json, status, latency_ms, token_usage, cost_usd, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mission_id, task_id, span_id, parent_span_id, trace_type, actor,
                json.dumps(input_data), json.dumps(output_data), status, float(latency_ms),
                int(token_usage), float(cost_usd), utc_now(),
            ),
        )

    def list_traces(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT * FROM traces WHERE mission_id=? ORDER BY id", (mission_id,))
        result = []
        for row in rows:
            item = dict(row)
            item["input"] = decode_json(item.pop("input_json"), {})
            item["output"] = decode_json(item.pop("output_json"), {})
            result.append(item)
        return result

    def add_metric(self, mission_id: str, task_id: str | None, metric_type: str, value: float, unit: str, dimensions: dict[str, Any] | None = None) -> int:
        return self.db.execute(
            """INSERT INTO metrics(mission_id, task_id, metric_type, value, unit, dimensions_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mission_id, task_id, metric_type, float(value), unit, json.dumps(dimensions or {}), utc_now()),
        )

    def list_metrics(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT * FROM metrics WHERE mission_id=? ORDER BY id", (mission_id,))
        result = []
        for row in rows:
            item = dict(row)
            item["dimensions"] = decode_json(item.pop("dimensions_json"), {})
            result.append(item)
        return result

    def add_checkpoint(self, mission_id: str, task_id: str | None, state: dict[str, Any]) -> int:
        return self.db.execute(
            "INSERT INTO checkpoints(mission_id, task_id, state_json, created_at) VALUES (?, ?, ?, ?)",
            (mission_id, task_id, json.dumps(state), utc_now()),
        )

    def latest_checkpoint(self, mission_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM checkpoints WHERE mission_id=? ORDER BY id DESC LIMIT 1", (mission_id,))
        if not row:
            return None
        item = dict(row)
        item["state"] = decode_json(item.pop("state_json"), {})
        return item

    # Idempotency ---------------------------------------------------------------
    def get_idempotent_result(self, key: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT result_json FROM idempotency_keys WHERE key=?", (key,))
        return decode_json(row["result_json"], {}) if row else None

    def save_idempotent_result(self, key: str, scope: str, result: dict[str, Any]) -> None:
        try:
            self.db.execute(
                "INSERT INTO idempotency_keys(key, scope, result_json, created_at) VALUES (?, ?, ?, ?)",
                (key, scope, json.dumps(result), utc_now()),
            )
        except Exception:
            # Concurrent duplicate writes are safe; the first durable result wins.
            pass

    # Tamper-evident audit -------------------------------------------------------
    def add_audit(self, mission_id: str | None, category: str, actor: str, action: str, outcome: str, details: dict[str, Any]) -> int:
        row = self.db.fetchone(
            "SELECT sequence, record_hash FROM audit_log WHERE mission_id IS ? ORDER BY id DESC LIMIT 1",
            (mission_id,),
        )
        sequence = int(row["sequence"] + 1) if row else 1
        previous_hash = str(row["record_hash"]) if row else "GENESIS"
        created_at = utc_now()
        canonical = json.dumps({
            "mission_id": mission_id,
            "sequence": sequence,
            "previous_hash": previous_hash,
            "category": category,
            "actor": actor,
            "action": action,
            "outcome": outcome,
            "details": details,
            "created_at": created_at,
        }, sort_keys=True, separators=(",", ":"))
        record_hash = hmac.new(self.audit_secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        return self.db.execute(
            """INSERT INTO audit_log(mission_id, sequence, previous_hash, record_hash, category, actor,
               action, outcome, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mission_id, sequence, previous_hash, record_hash, category, actor, action, outcome, json.dumps(details), created_at),
        )

    def list_audit(self, mission_id: str | None) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM audit_log WHERE mission_id IS ? ORDER BY id", (mission_id,)
        )
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = decode_json(item.pop("details_json"), {})
            result.append(item)
        return result

    def verify_audit_chain(self, mission_id: str | None) -> dict[str, Any]:
        records = self.list_audit(mission_id)
        previous_hash = "GENESIS"
        valid = True
        broken_at: int | None = None
        for record in records:
            canonical = json.dumps({
                "mission_id": record["mission_id"],
                "sequence": record["sequence"],
                "previous_hash": record["previous_hash"],
                "category": record["category"],
                "actor": record["actor"],
                "action": record["action"],
                "outcome": record["outcome"],
                "details": record["details"],
                "created_at": record["created_at"],
            }, sort_keys=True, separators=(",", ":"))
            expected = hmac.new(self.audit_secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
            if record["previous_hash"] != previous_hash or not hmac.compare_digest(expected, record["record_hash"]):
                valid = False
                broken_at = record["sequence"]
                break
            previous_hash = record["record_hash"]
        return {"valid": valid, "records": len(records), "broken_at_sequence": broken_at, "head_hash": previous_hash}
