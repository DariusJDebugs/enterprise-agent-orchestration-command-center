from __future__ import annotations

import re
from typing import Any


CITATION_RE = re.compile(r"DOC-(\d+)#CHUNK-(\d+)")


class EvaluationService:
    def validate_citations(self, report: str, available_chunks: list[dict[str, Any]]) -> dict[str, Any]:
        labels = {f"DOC-{chunk['document_id']}#CHUNK-{chunk['chunk_index'] + 1}" for chunk in available_chunks}
        used = set(CITATION_RE.findall(report))
        used_labels = {f"DOC-{doc}#CHUNK-{chunk}" for doc, chunk in used}
        invalid = sorted(used_labels - labels)
        return {
            "valid": not invalid and bool(used_labels),
            "citation_count": len(used_labels),
            "invalid_citations": invalid,
            "available_citations": len(labels),
        }

    def groundedness(self, report: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
        evidence_terms: set[str] = set()
        for citation in citations:
            evidence_terms.update(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", str(citation.get("excerpt", "")).lower()))
        claim_lines = [
            line.strip(" -*") for line in report.splitlines()
            if line.strip().startswith(("-", "*")) and len(line.strip()) > 20
        ]
        supported = 0
        details = []
        for claim in claim_lines:
            terms = set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", claim.lower()))
            overlap = len(terms & evidence_terms) / max(1, len(terms))
            is_supported = overlap >= 0.08 or "recommendation" in claim.lower() or "risk level" in claim.lower()
            supported += int(is_supported)
            details.append({"claim": claim[:180], "supported": is_supported, "overlap": round(overlap, 3)})
        score = round((supported / max(1, len(claim_lines))) * 100)
        return {"score": score, "supported_claims": supported, "total_claims": len(claim_lines), "details": details[:20]}

    def quality_gate(self, report: str, citations: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[str, Any]:
        citation = self.validate_citations(report, chunks)
        groundedness = self.groundedness(report, citations)
        required_sections = [
            "Executive decision", "Compliance", "Financial", "Operational", "Content-security", "Source evidence", "Human authorization",
        ]
        missing_sections = [section for section in required_sections if section.lower() not in report.lower()]
        passed = citation["valid"] and groundedness["score"] >= 30 and not missing_sections and len(report) >= 800
        return {
            "passed": passed,
            "citation_validation": citation,
            "groundedness": groundedness,
            "missing_sections": missing_sections,
            "report_length": len(report),
        }
