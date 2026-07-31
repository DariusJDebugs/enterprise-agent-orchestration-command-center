#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings
from app.operations import create_database_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an integrity-checked SQLite backup")
    parser.add_argument("--label", default="manual")
    parser.add_argument("--database")
    parser.add_argument("--backup-dir")
    args = parser.parse_args()
    settings = Settings.from_env()
    database = Path(args.database) if args.database else settings.database_path
    backup_dir = Path(args.backup_dir) if args.backup_dir else settings.backup_dir
    print(json.dumps(create_database_backup(database, backup_dir, args.label), indent=2))


if __name__ == "__main__":
    main()
