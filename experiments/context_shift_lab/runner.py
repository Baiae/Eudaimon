#!/usr/bin/env python3
"""Score submitted rankings on public, synthetic context-switch examples.

This is an evaluation demo, not Eudaimon's protected campaign evaluator.
It never imports or executes candidate code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STOPWORDS = frozenset({"a", "an", "and", "as", "at", "by", "for", "from", "in", "is", "of", "on", "or", "the", "to", "which", "with"})


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold())) - STOPWORDS


def load_suite(path: Path) -> dict:
    suite = json.loads(path.read_text(encoding="utf-8"))
    if suite.get("status") != "PUBLIC_DEMO_PROVISIONAL_LABELS":
        raise ValueError("suite must identify its public, provisional label status")
    pairs = suite.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("suite needs at least one pair")
    pair_ids, case_ids = set(), set()
    for pair in pairs:
        pid, items, contexts = pair["pair_id"], pair["items"], pair["contexts"]
        if pid in pair_ids or len(contexts) != 2 or len(items) < 2:
            raise ValueError("pair IDs must be unique, with exactly two contexts and at least two items")
        pair_ids.add(pid)
        ids = [item["id"] for item in items]
        if len(ids) != len(set(ids)) or any(not isinstance(item["text"], str) for item in items):
            raise ValueError("item IDs must be unique and each item must have text")
        gold = []
        for case in contexts:
            if case["case_id"] in case_ids or case["gold_id"] not in ids:
                raise ValueError("case IDs must be unique and gold IDs must exist in items")
            case_ids.add(case["case_id"])
            gold.append(case["gold_id"])
        if gold[0] == gold[1]:
            raise ValueError("a context-switch pair needs distinct expected first choices")
    return suite


def lexical_baseline(suite: dict) -> dict:
    """Plain goal/item token overlap; a diagnostic baseline, not a trained model."""
    predictions = []
    for pair in suite["pairs"]:
        for case in pair["contexts"]:
            goal = _tokens(case["goal"])
            ranked = sorted(pair["items"], key=lambda item: (-len(goal & _tokens(item["text"])), item["id"]))
            predictions.append({"case_id": case["case_id"], "ranked_ids": [item["id"] for item in ranked]})
    return {"model_name": "Goal-word overlap (diagnostic baseline)", "predictions": predictions}


def agent_prompts(suite: dict) -> dict:
    """Export only the public inputs; do not hand an agent labels or rationales."""
    return {"suite_name": suite["name"], "cases": [
        {"pair_id": pair["pair_id"], "case_id": case["case_id"], "goal": case["goal"],
         "items": pair["items"]}
        for pair in suite["pairs"] for case in pair["contexts"]
    ]}


def score(suite: dict, submission: dict) -> dict:
    """Reject missing/extra/invalid predictions; count a pair only if both are correct."""
    if not isinstance(submission.get("model_name"), str) or not submission["model_name"].strip():
        raise ValueError("model_name must be a nonempty string")
    predictions = submission.get("predictions")
    if not isinstance(predictions, list):
        raise ValueError("predictions must be a list")
    by_id = {}
    for pred in predictions:
        cid = pred["case_id"]
        if cid in by_id:
            raise ValueError(f"duplicate prediction: {cid}")
        by_id[cid] = pred
    expected = {case["case_id"] for pair in suite["pairs"] for case in pair["contexts"]}
    if set(by_id) != expected:
        raise ValueError(f"prediction IDs mismatch: missing={sorted(expected - set(by_id))}; extra={sorted(set(by_id) - expected)}")
    pair_results = []
    for pair in suite["pairs"]:
        ids = [item["id"] for item in pair["items"]]
        cases = []
        for case in pair["contexts"]:
            pred = by_id[case["case_id"]]
            ranked = pred["ranked_ids"]
            if not isinstance(ranked, list) or len(ranked) != len(ids) or set(ranked) != set(ids):
                raise ValueError(f"{case['case_id']}: ranked_ids must be an exact permutation of item IDs")
            confidence = pred.get("confidence")
            if confidence is not None and (type(confidence) not in (float, int) or not 0 <= confidence <= 1):
                raise ValueError(f"{case['case_id']}: confidence must be a number between 0 and 1")
            cases.append({"case_id": case["case_id"], "goal": case["goal"], "gold_id": case["gold_id"],
                          "reason": case["reason"], "ranked_ids": ranked, "chosen_id": ranked[0],
                          "correct": ranked[0] == case["gold_id"], "confidence": confidence})
        pair_results.append({"pair_id": pair["pair_id"], "title": pair["title"], "items": pair["items"],
                             "cases": cases, "switch_success": all(c["correct"] for c in cases)})
    success = sum(p["switch_success"] for p in pair_results)
    return {"model_name": submission["model_name"], "pairs_correct": success, "pairs_total": len(pair_results),
            "switch_success_rate": success / len(pair_results), "pairs": pair_results}


def build_report(suite_path: Path, submission: dict) -> dict:
    raw_suite = suite_path.read_bytes()
    suite = load_suite(suite_path)
    return {"title": "Context Shift Lab", "status": suite["status"], "suite_sha256": hashlib.sha256(raw_suite).hexdigest(),
            "suite_name": suite["name"], "method": "Both first choices must match the provisional labels for a pair to pass.",
            "candidate": score(suite, submission), "baseline": score(suite, lexical_baseline(suite))}


def write_html(report: dict, path: Path) -> None:
    template = (HERE / "report_template.html").read_text(encoding="utf-8")
    payload = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    path.write_text(template.replace("__REPORT_JSON__", payload), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=HERE / "demo_suite.json")
    parser.add_argument("--predictions", type=Path, help="JSON with model_name and a ranking for every case")
    parser.add_argument("--export-prompts", type=Path, help="write agent-facing inputs without answer keys, then exit")
    parser.add_argument("--html", type=Path, default=HERE / "report.html")
    parser.add_argument("--json", type=Path, help="optional machine-readable results path")
    args = parser.parse_args()
    try:
        if args.export_prompts:
            prompts = agent_prompts(load_suite(args.suite))
            args.export_prompts.write_text(json.dumps(prompts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"exported {len(prompts['cases'])} agent-facing cases to {args.export_prompts}")
            return 0
        if args.predictions is None:
            parser.error("--predictions is required unless --export-prompts is used")
        submission = json.loads(args.predictions.read_text(encoding="utf-8"))
        report = build_report(args.suite, submission)
        write_html(report, args.html)
        if args.json:
            args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"{report['candidate']['pairs_correct']}/{report['candidate']['pairs_total']} pairs passed; "
          f"baseline {report['baseline']['pairs_correct']}/{report['baseline']['pairs_total']}; "
          f"open {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
