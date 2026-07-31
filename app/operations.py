from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_database_backup(database_path: Path, backup_dir: Path, label: str | None = None) -> dict[str, str | int]:
    if not database_path.exists():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "" if not label else "-" + "".join(ch for ch in label if ch.isalnum() or ch in "-_")[:40]
    destination = backup_dir / f"command-center-{stamp}{safe_label}.db"
    with sqlite3.connect(database_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(database_path),
        "backup": str(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }
    destination.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def restore_database_backup(backup_path: Path, database_path: Path, expected_sha256: str | None = None) -> dict[str, str | int]:
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup does not exist: {backup_path}")
    actual = sha256_file(backup_path)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError("Backup checksum mismatch")
    with sqlite3.connect(backup_path) as source:
        result = source.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".restore-tmp")
    shutil.copy2(backup_path, temporary)
    temporary.replace(database_path)
    return {"restored": str(database_path), "source": str(backup_path), "sha256": actual, "size_bytes": database_path.stat().st_size}
