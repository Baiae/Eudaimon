#!/usr/bin/env python3
"""CLI adapter for the deterministic RR example evaluator."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _reviewed_policy_evaluator():
    # -I removes the campaign from sys.path; load the separately pinned policy
    # by its exact file path, never via a shadowable package/module name.
    policy_path = Path(__file__).with_name("rr_policy.py")
    spec = importlib.util.spec_from_file_location("_eudaimon_reviewed_policy", policy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("reviewed evaluator policy is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    if not args.candidate.is_file():
        print(json.dumps({"error": "candidate_not_found"}))
        return 2
    try:
        result = _reviewed_policy_evaluator()(args.candidate)
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"error": "candidate_read_failed", "detail": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
