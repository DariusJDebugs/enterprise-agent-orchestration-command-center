#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.operations import restore_database_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a verified SQLite backup")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--database")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    settings = Settings.from_env()
    destination = Path(args.database) if args.database else settings.database_path
    print(json.dumps(restore_database_backup(args.backup, destination, args.sha256), indent=2))


if __name__ == "__main__":
    main()
