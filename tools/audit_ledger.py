#!/usr/bin/env python3
"""Read-only structural audit of legacy JSONL evidence.

Detects malformed framing, event schemas and transaction linkage. Neither
SHA-256 candidate digests nor these checks authenticate the ledger itself.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


OUTCOMES = {"promotion_commit", "promotion_recovered_commit", "promotion_recovered_abort"}
EVENTS = OUTCOMES | {"promotion_intent", "baseline", "candidate", "evaluation_error", "halt"}


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_integer(value: object) -> bool:
    return type(value) is int and value > 0


def _finite_number(value: object) -> bool:
    if type(value) not in (float, int):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _object_with_unique_keys(pairs: list[tuple[str, object]]) -> dict:
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"duplicate JSON member: {key}")
        data[key] = value
    return data


def _reject_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON token: {token}")


def audit_ledger(path: Path) -> dict[str, object]:
    """Audit without ever opening the ledger in a write mode."""
    raw = path.read_bytes()
    issues: list[str] = []
    if raw and not raw.endswith(b"\n"):
        issues.append("last record is not newline-terminated (possible partial write)")
    intents: dict[str, dict] = {}
    completed: set[str] = set()
    successful: set[str] = set()
    seen_transaction_ids: set[str] = set()
    events = 0

    for number, line in enumerate(raw.split(b"\n"), 1):
        if not line and number == raw.count(b"\n") + 1:
            break  # expected trailing delimiter
        if not line.strip():
            issues.append(f"line {number}: blank record")
            continue
        try:
            record = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=_object_with_unique_keys,
                parse_constant=_reject_constant,
            )
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            issues.append(f"line {number}: invalid JSON or encoding ({exc})")
            continue

        if not isinstance(record, dict) or not _nonempty(record.get("event")):
            issues.append(f"line {number}: invalid event object")
            continue
        events += 1
        kind = record["event"]
        if kind not in EVENTS:
            issues.append(f"line {number}: unknown legacy event type {kind!r}")
            continue
        for field in ("run_id", "timestamp"):
            if not _nonempty(record.get(field)):
                issues.append(f"line {number}: missing or invalid {field}")

        if kind in ("baseline", "candidate", "evaluation_error"):
            if not _nonempty(record.get("candidate")):
                issues.append(f"line {number}: missing candidate")

        if kind in ("baseline", "candidate"):
            evaluation = record.get("evaluation")
            if not isinstance(evaluation, dict):
                issues.append(f"line {number}: invalid evaluation object")
            else:
                if type(evaluation.get("protect_pass")) is not bool:
                    issues.append(f"line {number}: invalid Protect Gate")
                score = evaluation.get("score")
                if not _finite_number(score):
                    issues.append(f"line {number}: invalid evaluation score")
                if "candidate_sha256" in evaluation and not _digest(evaluation["candidate_sha256"]):
                    issues.append(f"line {number}: invalid evaluated candidate_sha256")

        if kind == "halt":
            if not _nonempty(record.get("reason")) or not isinstance(record.get("state"), dict):
                issues.append(f"line {number}: halt reason/state missing or malformed")
        elif kind == "evaluation_error":
            if not _nonempty(record.get("error")):
                issues.append(f"line {number}: missing evaluation error")
        elif kind == "candidate":
            decision = record.get("decision")
            if not _positive_integer(record.get("iteration")):
                issues.append(f"line {number}: invalid candidate iteration")
            if decision not in ("rejected", "promoted"):
                issues.append(f"line {number}: invalid candidate decision")
            if decision == "promoted":
                tid = record.get("transaction_id")
                if not _nonempty(tid) or tid not in successful:
                    issues.append(f"line {number}: promoted candidate without successful promotion transaction")
                elif intents[tid].get("run_id") != record.get("run_id"):
                    issues.append(f"line {number}: promoted candidate references another run")
                elif (isinstance(record.get("evaluation"), dict)
                      and record["evaluation"].get("candidate_sha256") != intents[tid].get("candidate_sha256")):
                    issues.append(f"line {number}: promoted candidate digest disagrees with intent")
            elif "transaction_id" in record:
                issues.append(f"line {number}: rejected candidate contains transaction ID")

        if kind == "promotion_intent":
            tid = record.get("transaction_id")
            if not _nonempty(tid) or tid in seen_transaction_ids:
                issues.append(f"line {number}: missing, duplicate or reused promotion intent ID")
            else:
                seen_transaction_ids.add(tid)
                intents[tid] = record
            for field in ("old_target_sha256", "candidate_sha256"):
                if not _digest(record.get(field)):
                    issues.append(f"line {number}: invalid {field}")
            if (record.get("old_target_sha256") == record.get("candidate_sha256")
                    and _digest(record.get("old_target_sha256"))):
                issues.append(f"line {number}: ambiguous intent with equal old/candidate digests")
        elif kind in OUTCOMES:
            tid = record.get("transaction_id")
            if not _nonempty(tid) or tid not in intents or tid in completed:
                issues.append(f"line {number}: unmatched or repeated promotion outcome")
            else:
                intent = intents[tid]
                if record.get("run_id") != intent.get("run_id"):
                    issues.append(f"line {number}: outcome run_id differs from intent")
                field = "target_sha256" if kind == "promotion_commit" else "recovered_target_sha256"
                expected = (intent.get("old_target_sha256") if kind == "promotion_recovered_abort"
                            else intent.get("candidate_sha256"))
                if not _digest(record.get(field)) or record.get(field) != expected:
                    issues.append(f"line {number}: {field} does not match intent digest")
                completed.add(tid)
                if (kind in ("promotion_commit", "promotion_recovered_commit")
                        and record.get("run_id") == intent.get("run_id")
                        and _digest(record.get(field)) and record[field] == expected):
                    successful.add(tid)

    return {
        "records": events,
        "pending_transactions": sorted(set(intents) - completed),
        "issues": issues,
        "integrity_level": "STRUCTURAL_ONLY_NOT_TAMPER_PROOF",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    report = audit_ledger(args.ledger)
    print(json.dumps(report, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
