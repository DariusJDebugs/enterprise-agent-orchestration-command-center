from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class InjectionFinding:
    pattern_id: str
    severity: str
    excerpt: str
    start: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "excerpt": self.excerpt,
            "start": self.start,
        }


@dataclass(slots=True)
class SecurityScan:
    status: str
    risk_score: int
    findings: list[InjectionFinding]
    quarantined: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "risk_score": self.risk_score,
            "findings": [finding.as_dict() for finding in self.findings],
            "quarantined": self.quarantined,
        }


class PromptInjectionDetector:
    """Deterministic content firewall for retrieved and uploaded text.

    It intentionally errs on the side of isolation. Suspect chunks remain in the
    evidence store for forensics but are excluded from normal retrieval.
    """

    PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
        ("ignore_policy", "critical", re.compile(r"\b(ignore|disregard|override)\b.{0,60}\b(previous|prior|system|developer|policy|instructions?)\b", re.I | re.S)),
        ("system_prompt_exfiltration", "critical", re.compile(r"\b(reveal|print|show|leak|expose)\b.{0,50}\b(system prompt|developer message|hidden instructions?|secrets?)\b", re.I | re.S)),
        ("tool_execution", "high", re.compile(r"\b(run|execute|invoke|call)\b.{0,45}\b(shell|terminal|powershell|bash|tool|function|connector|api)\b", re.I | re.S)),
        ("credential_request", "critical", re.compile(r"\b(api key|password|credential|access token|private key|secret key)\b.{0,45}\b(send|copy|upload|return|exfiltrate|reveal)\b", re.I | re.S)),
        ("role_impersonation", "high", re.compile(r"\b(you are now|act as|pretend to be)\b.{0,60}\b(admin|administrator|system|developer|security officer)\b", re.I | re.S)),
        ("approval_bypass", "critical", re.compile(r"\b(bypass|skip|disable|circumvent)\b.{0,50}\b(approval|authorization|permission|guardrail|security|policy)\b", re.I | re.S)),
        ("encoded_instruction", "medium", re.compile(r"\b(base64|rot13|decode this|hidden payload)\b", re.I)),
        ("instruction_delimiter", "medium", re.compile(r"(<\|system\|>|\[SYSTEM\]|BEGIN SYSTEM PROMPT|### SYSTEM INSTRUCTION)", re.I)),
    )

    WEIGHTS = {"medium": 20, "high": 38, "critical": 55}

    def scan(self, text: str) -> SecurityScan:
        findings: list[InjectionFinding] = []
        for pattern_id, severity, pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 80)
                excerpt = re.sub(r"\s+", " ", text[start:end]).strip()
                findings.append(InjectionFinding(pattern_id, severity, excerpt[:240], match.start()))
        score = min(100, sum(self.WEIGHTS[finding.severity] for finding in findings))
        quarantined = any(finding.severity in {"high", "critical"} for finding in findings)
        status = "quarantined" if quarantined else ("review" if findings else "clean")
        return SecurityScan(status=status, risk_score=score, findings=findings, quarantined=quarantined)
