#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a high-entropy deployment secret")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bytes", type=int, default=48)
    args = parser.parse_args()
    value = secrets.token_urlsafe(max(32, args.bytes))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value + "\n", encoding="utf-8")
        args.output.chmod(0o600)
        print(args.output)
    else:
        print(value)


if __name__ == "__main__":
    main()
