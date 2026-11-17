# Eudaimon

Eudaimon is an AGI+W (Artificial General Intelligence + Wisdom) research
architecture. Its authoritative **conceptual blueprint** is preserved in
`spec/conceptual/` from public GitHub commit `9c464796`. AutoResearch-W is
the proposed self-improvement research subsystem. The code under `engine/`
is a **constrained reference implementation**, not the complete blueprint.

This repository contains the original conceptual design plus a bounded,
deterministic reference sketch. It does not implement AGI, consciousness, life, or autonomous wisdom,
and its example evaluator is a toy contract checker rather than evidence of
capability.

## Architectural authority and scope

1. `spec/conceptual/` — **CANONICAL CONCEPTUAL BLUEPRINT**. Original public
   design files are retained byte-for-byte with SHA-256 provenance in
   `SOURCE_MANIFEST.json`. This designation is conceptual authority, not a
   claim that every design requirement is implemented.
2. `docs/1-architecture.md` through `docs/6-failure-modes.md` —
   **REFERENCE IMPLEMENTATION CONTRACTS**, scoped to the current example.
   They do not replace or amend the original conceptual blueprint.
3. `engine/`, `campaigns/`, `tests/` — **IMPLEMENTED REFERENCE**, with
   bounded evaluation and explicit unresolved security limitations.
4. `docs/7-remediation-spec.md` through `docs/9-semantic-reconciliation.md`
   — remediation evidence and unresolved architectural decisions.

**Safety boundary:** the evaluator is not securely sandboxed. By default the
engine permits only the SHA-256-pinned, bundled reference evaluator **and** its
campaign-local `rr_policy.py`; changes to either are refused until reviewed and
re-pinned. Custom evaluator approval is available to programmatic callers via
`EngineConfig.trusted_evaluator_sha256` and is an explicit trust decision, not a
sandbox. A same-user attacker can still race filesystem operations, and memory,
filesystem, and network isolation are not provided. Do not run untrusted code.
The legacy ledger audit is **structural-only**, not cryptographic authentication.
No implementation of the full AGI+W blueprint is claimed.

## Repository layout

```text
spec/
  conceptual/                # preserved canonical conceptual blueprint
docs/
  1-architecture.md
  2-frameworks.md
  3-autoresearch-w.md
  5-eval-runner.md
  6-failure-modes.md
campaigns/
  rr_engine/
    program.md
    eval_runner.py
    rr_policy.py
    proposals/
engine/
  engine.py
tests/
  test_engine.py
```

Read the conceptual design documents in `spec/conceptual/` first, then
the narrower local reference contracts in `docs/`. The implementation is
stdlib-only and is intentionally small enough to inspect end to end.

## Run the reference campaign

From the repository root:

```bash
python3 engine/engine.py campaigns/rr_engine
```

The engine evaluates the baseline and any files placed directly in
`campaigns/rr_engine/proposals/`. It promotes only a candidate that passes the
Protect Gate and improves the scalar score. It records every decision in
`campaigns/rr_engine/.autoresearch/ledger.jsonl` and the latest state in
`state.json`. Those generated files are ignored by Git.

To run bounded tests:

```bash
python3 -m unittest discover -s tests -v
```

## Campaign contract

Each campaign has exactly one mutable target file, `program.md`, and a local
`eval_runner.py`. The engine owns iteration limits, evaluation failures,
promotion, and halts. The evaluator reports a single scalar score plus a
Protect Gate result; it does not decide whether the campaign continues.

The example campaign is a deterministic reference policy only. A different
domain evaluator requires an explicit source/dependency review and a deliberate
trust-pin change; unreviewed replacements are rejected. Do not use these example
scores to draw real research conclusions.
