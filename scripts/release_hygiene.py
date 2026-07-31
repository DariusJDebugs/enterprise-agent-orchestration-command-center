#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "release_evidence" / "GITHUB_HYGIENE_SCAN.json"

TEXT_SUFFIXES = {
    "", ".md", ".txt", ".py", ".js", ".css", ".html", ".json", ".toml", ".yml", ".yaml",
    ".sh", ".mmd", ".svg", ".example", ".gitignore", ".dockerignore", ".gitattributes",
}
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
ALLOWED_RUNTIME_PLACEHOLDERS = {
    Path("data/.gitkeep"), Path("data/uploads/.gitkeep"), Path("data/backups/.gitkeep"), Path("secrets/.gitkeep")
}
FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"(^|/)secrets/(?!\.gitkeep$)"),
    re.compile(r"(^|/)data/(?:uploads|backups)/(?!.gitkeep$)"),
    re.compile(r"\.(?:db|sqlite|sqlite3|db-wal|db-shm)$", re.I),
    re.compile(r"\.(?:zip|7z|tar|gz|mp4|mov|webm)$", re.I),
]
PRIVATE_PATTERNS = {
    "mounted_sandbox_path": re.compile(re.escape("/mnt/" + "data/"), re.I),
    "user_home_path": re.compile(r"/(?:home|Users)/[^/\s]+/", re.I),
    "windows_user_path": re.compile(r"[A-Z]:\\(?:Users|Documents and Settings)\\[^\\\s]+", re.I),
    "wsl_path": re.compile(r"\\\\wsl(?:\$)?\\", re.I),
    "personal_actor": re.compile(r"\b[A-Z][A-Za-z0-9._-]{1,60}-local-operator\b"),
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}
STALE_PUBLIC_CLAIMS = {
    "app/static/index.html": ["PHASE 2 EVIDENCE"],
    "app/static/app.js": ["-local-operator"],
    "README.md": ["9 specialist agents", "4 registered tools"],
}
MAX_SOURCE_FILE_BYTES = 5 * 1024 * 1024


def iter_files():
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(PROJECT_ROOT)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        yield path, rel


def is_text(path: Path) -> bool:
    if path.name in {".gitignore", ".dockerignore", ".gitattributes", "Dockerfile", "Makefile"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def scan() -> dict[str, object]:
    findings: list[dict[str, object]] = []
    files = list(iter_files())
    for path, rel in files:
        rel_s = rel.as_posix()
        if rel not in ALLOWED_RUNTIME_PLACEHOLDERS and rel_s not in {".env.example", ".env.production.example"}:
            for pattern in FORBIDDEN_FILE_PATTERNS:
                if pattern.search(rel_s):
                    findings.append({"type": "forbidden_artifact", "file": rel_s, "detail": pattern.pattern})
                    break
        if path.stat().st_size > MAX_SOURCE_FILE_BYTES:
            findings.append({"type": "oversized_source_file", "file": rel_s, "bytes": path.stat().st_size})
        if not is_text(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append({"type": "unexpected_binary_text", "file": rel_s})
            continue
        for name, pattern in PRIVATE_PATTERNS.items():
            if rel_s == "scripts/release_hygiene.py":
                continue
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                findings.append({"type": name, "file": rel_s, "line": line, "match": match.group(0)[:120]})
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                findings.append({"type": name, "file": rel_s, "line": line, "match": match.group(0)[:16] + "…"})
        for stale in STALE_PUBLIC_CLAIMS.get(rel_s, []):
            if stale in content:
                findings.append({"type": "stale_public_claim", "file": rel_s, "match": stale})

    required = [
        "README.md", ".gitignore", ".dockerignore", ".gitattributes", "SECURITY.md",
        "docs/CHALLENGE_ALIGNMENT.md", "docs/REQUIREMENTS_EVIDENCE_MATRIX.md",
        "docs/EVALUATOR_QUICKSTART.md", "docs/ARCHITECTURE.md", "docs/THREAT_MODEL.md",
        "docs/TEST_RESULTS_REPORT.md", "docs/assets/screenshots/01_command_overview.png",
    ]
    missing = [name for name in required if not (PROJECT_ROOT / name).exists()]
    for name in missing:
        findings.append({"type": "missing_required_publication_file", "file": name})

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not findings else "FAIL",
        "files_scanned": len(files),
        "source_bytes": sum(path.stat().st_size for path, _ in files),
        "checks": [
            "private filesystem paths", "personal identifiers", "credential patterns", "forbidden runtime artifacts",
            "oversized release media", "stale interface claims", "required publication files",
        ],
        "findings": findings,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan the public source tree for GitHub release-hygiene failures.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when findings exist.")
    parser.add_argument("--write-report", action="store_true", help="Write the machine-readable report.")
    args = parser.parse_args()
    result = scan()
    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"RELEASE HYGIENE {result['status']} — {result['files_scanned']} files scanned")
    if result["findings"]:
        print(json.dumps(result["findings"], indent=2))
    if args.check and result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
