from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.services import build_services



def main() -> None:
    services = build_services(Settings.from_env())
    for path in sorted((PROJECT_ROOT / "sample_docs").glob("*")):
        if path.is_file():
            result = services.rag.ingest(path.name, "text/markdown", path.read_bytes(), trust_state="trusted")
            print(f"{path.name}: {result['chunk_count']} chunks (duplicate={result['duplicate']})")
    print(f"Total documents: {len(services.repository.list_documents())}")


if __name__ == "__main__":
    main()
