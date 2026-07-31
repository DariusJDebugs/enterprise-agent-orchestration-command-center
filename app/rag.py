from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .embeddings import HashEmbeddingModel
from .repository import Repository, utc_now
from .security import PromptInjectionDetector


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_name: str
    chunk_index: int
    content: str
    score: float
    citation: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "score": round(self.score, 4),
            "citation": self.citation,
            "metadata": self.metadata,
        }


class DocumentParser:
    TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".log", ".yaml", ".yml"}

    @classmethod
    def parse(cls, filename: str, content_type: str, data: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in cls.TEXT_EXTENSIONS or content_type.startswith("text/"):
            return cls._decode_text(data)
        if suffix == ".json" or content_type == "application/json":
            parsed = json.loads(cls._decode_text(data))
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        if suffix == ".csv" or content_type in {"text/csv", "application/csv"}:
            return cls._parse_csv(data)
        if suffix == ".pdf" or content_type == "application/pdf":
            return cls._parse_pdf(data)
        if suffix == ".docx" or content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return cls._parse_docx(data)
        raise ValueError(f"Unsupported document type: {suffix or content_type}")

    @staticmethod
    def _decode_text(data: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Unable to decode text document")

    @classmethod
    def _parse_csv(cls, data: bytes) -> str:
        text = cls._decode_text(data)
        reader = csv.reader(io.StringIO(text))
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in reader)

    @staticmethod
    def _parse_pdf(data: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise ValueError("PDF support requires pypdf") from exc
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"[Page {index}]\n{text}")
        return "\n\n".join(pages)

    @staticmethod
    def _parse_docx(data: bytes) -> str:
        try:
            from docx import Document
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise ValueError("DOCX support requires python-docx") from exc
        document = Document(io.BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())


class RAGService:
    def __init__(
        self,
        repository: Repository,
        embedding_model: HashEmbeddingModel,
        *,
        chunk_size: int = 900,
        chunk_overlap: int = 150,
        injection_detector: PromptInjectionDetector | None = None,
    ):
        self.repository = repository
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.injection_detector = injection_detector or PromptInjectionDetector()

    def ingest(self, filename: str, content_type: str, data: bytes, trust_state: str = "untrusted") -> dict[str, Any]:
        checksum = hashlib.sha256(data).hexdigest()
        existing = self.repository.get_document_by_checksum(checksum)
        if existing:
            return {**existing, "duplicate": True, "chunk_count": self._document_chunk_count(existing["id"])}

        text = DocumentParser.parse(filename, content_type, data)
        text = self._normalize(text)
        if len(text) < 20:
            raise ValueError("Document contains too little extractable text")

        chunks = self._chunk(text)
        scans = [self.injection_detector.scan(chunk) for chunk in chunks]
        quarantined_count = sum(scan.quarantined for scan in scans)
        aggregate_findings = [finding for scan in scans for finding in scan.as_dict()["findings"]]
        security_status = "quarantined" if quarantined_count else ("review" if aggregate_findings else "clean")
        document_id = self.repository.create_document(
            name=filename,
            content_type=content_type or "application/octet-stream",
            checksum=checksum,
            size_bytes=len(data),
            trust_state=trust_state,
            security_status=security_status,
            security_findings=aggregate_findings,
        )
        now = utc_now()
        rows: list[tuple] = []
        for index, (chunk, scan) in enumerate(zip(chunks, scans, strict=True)):
            vector = self.embedding_model.embed(chunk)
            metadata = {
                "filename": filename,
                "char_start": index * max(1, self.chunk_size - self.chunk_overlap),
                "citation": f"DOC-{document_id}#CHUNK-{index + 1}",
                "trust_state": trust_state,
                "security_scan": scan.as_dict(),
                "quarantined": scan.quarantined,
            }
            rows.append((document_id, index, chunk, json.dumps(vector), json.dumps(metadata), now))
            if scan.findings:
                self.repository.add_security_incident(
                    document_id=document_id,
                    incident_type="prompt_injection_detected",
                    severity="critical" if any(f.severity == "critical" for f in scan.findings) else "high",
                    status="quarantined" if scan.quarantined else "review",
                    details={"filename": filename, "chunk_index": index, "scan": scan.as_dict()},
                )
        self.repository.create_chunks(rows)
        return {
            "id": document_id, "name": filename, "content_type": content_type, "checksum": checksum,
            "size_bytes": len(data), "chunk_count": len(chunks), "duplicate": False,
            "trust_state": trust_state, "security_status": security_status,
            "quarantined_chunks": quarantined_count, "security_findings": aggregate_findings,
        }

    def search(self, query: str, top_k: int = 6, include_quarantined: bool = False) -> list[RetrievedChunk]:
        query_vector = self.embedding_model.embed(query)
        candidates = []
        query_terms = set(re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", query.lower()))
        for chunk in self.repository.list_chunks(include_quarantined=include_quarantined):
            semantic = self.embedding_model.cosine_similarity(query_vector, chunk["vector"])
            content_terms = set(re.findall(r"[a-z0-9][a-z0-9_\-]{1,}", chunk["content"].lower()))
            lexical = len(query_terms & content_terms) / max(1, len(query_terms))
            score = (semantic * 0.78) + (lexical * 0.22)
            metadata = chunk["metadata"]
            citation = metadata.get("citation") or f"DOC-{chunk['document_id']}#CHUNK-{chunk['chunk_index'] + 1}"
            candidates.append(RetrievedChunk(
                chunk_id=chunk["id"],
                document_id=chunk["document_id"],
                document_name=chunk["document_name"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                score=score,
                citation=citation,
                metadata=metadata,
            ))
        candidates.sort(key=lambda item: item.score, reverse=True)
        return [item for item in candidates[:top_k] if item.score > 0.015]

    def _document_chunk_count(self, document_id: int) -> int:
        return sum(1 for chunk in self.repository.list_chunks() if chunk["document_id"] == document_id)

    def _chunk(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 <= self.chunk_size:
                current = f"{current}\n\n{paragraph}".strip()
                continue
            if current:
                chunks.append(current)
                overlap = current[-self.chunk_overlap:] if self.chunk_overlap else ""
                current = f"{overlap}\n\n{paragraph}".strip()
            else:
                start = 0
                while start < len(paragraph):
                    end = start + self.chunk_size
                    chunks.append(paragraph[start:end])
                    start = max(end - self.chunk_overlap, start + 1)
                current = ""
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
