#!/usr/bin/env python3
from __future__ import annotations

import json
from app.config import Settings
from app.database import Database


def main() -> None:
    settings = Settings.from_env()
    settings.ensure_directories()
    database = Database(settings.database_path)
    print(json.dumps(database.check(), indent=2))


if __name__ == "__main__":
    main()
