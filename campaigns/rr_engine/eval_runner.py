#!/usr/bin/env python3
"""CLI adapter for the deterministic RR example evaluator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rr_policy import evaluate_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    if not args.candidate.is_file():
        print(json.dumps({"error": "candidate_not_found"}))
        return 2
    try:
        result = evaluate_file(args.candidate)
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"error": "candidate_read_failed", "detail": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
