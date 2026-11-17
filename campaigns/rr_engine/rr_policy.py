"""Deterministic toy policy for the RR reference campaign.

This module is intentionally a document-contract checker. It is not a model,
an alignment proof, or an AGI+W evaluator.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable


EVALUATOR_VERSION = "rr-policy-example-0.1"
PROTECT_BYPASS_SENTINEL = "PROTECT_GATE_BYPASS"

PROTECT_PHRASES = (
    "fail closed",
    "protect gate",
    "engine decides halts",
)

CONTRACT_PHRASES = (
    "one scalar metric",
    "geometric mean",
    "held-out split",
)

SAFETY_PHRASES = (
    "fail closed",
    "cannot permit a proposal to rewrite the evaluator",
    "causes a halt",
)

TRACEABILITY_PHRASES = (
    "run_id",
    "jsonl ledger",
    "candidate digest",
)

HELD_OUT_PHRASES = (
    "one target file",
    "proposal",
    "evaluator error",
)


def _coverage(text: str, phrases: Iterable[str]) -> float:
    phrases = tuple(phrases)
    if not phrases:
        return 1.0
    lowered = text.casefold()
    return sum(phrase.casefold() in lowered for phrase in phrases) / len(phrases)


def _geometric_mean(values: Iterable[float]) -> float:
    values = tuple(float(value) for value in values)
    if not values or any(value < 0 or not math.isfinite(value) for value in values):
        return 0.0
    if any(value == 0 for value in values):
        return 0.0
    return math.prod(values) ** (1.0 / len(values))


def evaluate_text(text: str) -> dict[str, object]:
    """Return the example Protect Gate, components, and scalar score."""

    protect_pass = (
        PROTECT_BYPASS_SENTINEL not in text
        and _coverage(text, PROTECT_PHRASES) == 1.0
    )
    components = {
        "contract": _coverage(text, CONTRACT_PHRASES),
        "safety": _coverage(text, SAFETY_PHRASES),
        "traceability": _coverage(text, TRACEABILITY_PHRASES),
        "held_out": _coverage(text, HELD_OUT_PHRASES),
    }
    score = _geometric_mean(components.values())
    return {
        "protect_pass": protect_pass,
        "score": score,
        "components": components,
        "evaluator_version": EVALUATOR_VERSION,
    }


def evaluate_file(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    result = evaluate_text(data.decode("utf-8"))
    result["candidate_sha256"] = hashlib.sha256(data).hexdigest()
    result["candidate_bytes"] = len(data)
    return result
